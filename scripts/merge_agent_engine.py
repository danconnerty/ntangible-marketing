#!/usr/bin/env python3
"""One-time migration: import agent-engine brain into ntangible_marketing."""

import json as _json
import re
import uuid
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from sqlalchemy import text


def _ensure_dict(val):
    """Ensure a value is a dict — psycopg2 may return JSONB as str."""
    if isinstance(val, str):
        try:
            return _json.loads(val)
        except (ValueError, TypeError):
            return {}
    return val if isinstance(val, dict) else {}

from app.database import SessionLocal

AGENT_ENGINE_DSN = "postgresql://elliot18@localhost:5432/agent_engine"

# ── Agent-engine internal dedup: canonical_name -> list of duplicate names ──
PERSON_DEDUP = {
    "Pranay Ramash": ["Pranay R", "Pranay R.", "Pranay R22", "Patel Shalin"],
    "Isaac Sullivan": ["Isaac"],
    "Howard Schwartz": ["Howie Schwartz"],
    "Elliot Sones": ["Elliot (Form Submitter)", "elliotsenos16@gmail.com"],
}
COMPANY_ORG_DEDUP = {
    "NTangible": ["NTangible Inc."],
    "Alliance Fastpitch": ["The Alliance Fastpitch LLC", "Alliance"],
    "HRMC": ["HRMC Inc."],
    "Honsberger Physiotherapy & Biomechanics": ["Honsberger Physio+"],
    "1871": ["1871 Innovation Lab"],
    "MaRS": ["MaRS Accelerator"],
    "Future Stars Series": ["FSS"],
}

# ── Cross-DB dedup: marketing canonical_name -> agent-engine canonical_name(s) ──
CROSS_DB_MATCHES = {
    "Alliance Fastpitch": ["Alliance Fastpitch", "The Alliance Fastpitch LLC", "Alliance"],
    "Future Stars Series": ["Future Stars Series", "FSS"],
    "High Level Throwing": ["High Level Throwing"],
    "RFK Racing": ["RFK Racing"],
    "Boston College": ["Boston College"],
    "Michigan State": ["Michigan State University"],
    "Hofstra": ["Hofstra University"],
    "S2 Cognition": ["S2 Cognition"],
    "Scorability": ["Scorability"],
}

# ── Marketing role -> relationship edge ──
ROLE_TO_RELATION = {
    "partner": "partner_of",
    "client": "client_of",
    "competitor": "competes_with",
}


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def main():
    ae_conn = psycopg2.connect(AGENT_ENGINE_DSN)
    ae_conn.set_session(readonly=True)
    ae = ae_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    db = SessionLocal()

    try:
        _run_migration(ae, db)
        db.commit()
        print("Migration committed successfully.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        ae.close()
        ae_conn.close()


def _run_migration(ae, db):
    # Step 1: Load agent-engine entities
    ae.execute("SELECT id, entity_type, canonical_name, description, status, metadata FROM entity_nodes WHERE status = 'active'")
    ae_entities = {row["id"]: row for row in ae.fetchall()}

    # Step 2: Load agent-engine edges to find people with connections
    ae.execute("SELECT from_entity_id, to_entity_id FROM entity_edges")
    ae_edge_rows = ae.fetchall()
    connected_entity_ids = set()
    for row in ae_edge_rows:
        connected_entity_ids.add(row["from_entity_id"])
        connected_entity_ids.add(row["to_entity_id"])

    # Step 3: Build internal dedup map (agent-engine duplicate name -> canonical agent-engine ID)
    all_dedup = {**PERSON_DEDUP, **COMPANY_ORG_DEDUP}
    ae_by_name = {}
    for eid, row in ae_entities.items():
        ae_by_name.setdefault(row["canonical_name"], []).append(row)

    # Map: agent-engine UUID -> canonical agent-engine UUID
    ae_id_remap = {}
    for canonical_name, dupes in all_dedup.items():
        canonical_rows = ae_by_name.get(canonical_name, [])
        if not canonical_rows:
            continue
        canonical_id = canonical_rows[0]["id"]
        for dupe_name in dupes:
            for dupe_row in ae_by_name.get(dupe_name, []):
                ae_id_remap[dupe_row["id"]] = canonical_id

    # Step 4: Filter — skip noise person entities (no edges) and duplicates
    skip_ids = set(ae_id_remap.keys())
    import_entities = {}
    for eid, row in ae_entities.items():
        if eid in skip_ids:
            continue
        if row["entity_type"] == "person" and eid not in connected_entity_ids:
            continue
        import_entities[eid] = row
    print(f"Entities to import: {len(import_entities)} (filtered from {len(ae_entities)})")

    # Step 5: Load marketing entities for cross-DB dedup
    mkt_rows = db.execute(text("SELECT id, entity_type, canonical_name, slug FROM entity_nodes")).fetchall()
    mkt_by_name = {row.canonical_name: row for row in mkt_rows}

    # Build cross-DB remap: agent-engine UUID -> marketing UUID
    cross_remap = {}
    for mkt_name, ae_names in CROSS_DB_MATCHES.items():
        mkt_row = mkt_by_name.get(mkt_name)
        if not mkt_row:
            continue
        for ae_name in ae_names:
            for ae_row in ae_by_name.get(ae_name, []):
                cross_remap[ae_row["id"]] = mkt_row.id
                for dupe_id, canon_id in ae_id_remap.items():
                    if canon_id == ae_row["id"]:
                        cross_remap[dupe_id] = mkt_row.id

    # Combined remap
    def resolve(ae_id):
        resolved = ae_id_remap.get(ae_id, ae_id)
        return cross_remap.get(resolved, resolved)

    # Step 6: Find or create NTangible entity in marketing DB
    ntangible_row = mkt_by_name.get("NTangible")
    if not ntangible_row:
        ntangible_id = uuid.uuid4()
        db.execute(text("""
            INSERT INTO entity_nodes (id, entity_type, canonical_name, slug, status, primary_topic_key, metadata)
            VALUES (:id, 'company', 'NTangible', 'ntangible', 'active', NULL, '{"source": "agent_engine"}')
        """), {"id": str(ntangible_id)})
        print("Created NTangible entity node.")
    else:
        ntangible_id = ntangible_row.id

    # Map all agent-engine NTangible variants to the marketing NTangible node
    for ae_row in ae_by_name.get("NTangible", []):
        cross_remap[ae_row["id"]] = ntangible_id
    for ae_row in ae_by_name.get("NTangible Inc.", []):
        cross_remap[ae_row["id"]] = ntangible_id

    # Step 7: Import non-overlapping entities
    imported_count = 0
    for eid, row in import_entities.items():
        final_id = resolve(eid)
        if final_id != eid:
            continue
        existing = db.execute(text("SELECT id FROM entity_nodes WHERE id = :id"), {"id": str(eid)}).fetchone()
        if existing:
            continue
        meta = _ensure_dict(row["metadata"])
        meta["source"] = "agent_engine"
        # Generate unique slug — append entity_type if collision
        base_slug = slugify(row["canonical_name"])
        slug = base_slug
        slug_exists = db.execute(text(
            "SELECT 1 FROM entity_nodes WHERE entity_type = :et AND slug = :slug"
        ), {"et": row["entity_type"], "slug": slug}).fetchone()
        if slug_exists:
            slug = f"{base_slug}-{row['entity_type']}"
        db.execute(text("""
            INSERT INTO entity_nodes (id, entity_type, canonical_name, slug, description, status, primary_topic_key, metadata)
            VALUES (:id, :entity_type, :canonical_name, :slug, :description, :status, NULL, :metadata)
        """), {
            "id": str(eid),
            "entity_type": row["entity_type"],
            "canonical_name": row["canonical_name"],
            "slug": slug,
            "description": row["description"],
            "status": row["status"],
            "metadata": psycopg2.extras.Json(meta),
        })
        imported_count += 1
    print(f"Imported {imported_count} new entity nodes.")

    # Step 8: Merge metadata for overlapping entities (don't change entity_type)
    for ae_id, mkt_id in cross_remap.items():
        ae_row = ae_entities.get(ae_id)
        if not ae_row:
            continue
        db.execute(text("""
            UPDATE entity_nodes
            SET metadata = metadata || :extra,
                description = COALESCE(description, :desc)
            WHERE id = :id
        """), {
            "id": str(mkt_id),
            "extra": psycopg2.extras.Json({
                "agent_engine_id": str(ae_id),
                "agent_engine_type": ae_row["entity_type"],
                "source": "agent_engine",
            }),
            "desc": ae_row["description"],
        })

    # Step 9: Create role edges for overlapping entities
    for mkt_name, ae_names in CROSS_DB_MATCHES.items():
        mkt_row = mkt_by_name.get(mkt_name)
        if not mkt_row:
            continue
        relation = ROLE_TO_RELATION.get(mkt_row.entity_type)
        if not relation:
            continue
        existing_edge = db.execute(text("""
            SELECT id FROM entity_edges
            WHERE source_id = :src AND target_id = :tgt AND relation = :rel
        """), {"src": str(mkt_row.id), "tgt": str(ntangible_id), "rel": relation}).fetchone()
        if not existing_edge:
            db.execute(text("""
                INSERT INTO entity_edges (id, source_id, target_id, source_type, target_type, relation, confidence, metadata)
                VALUES (:id, :src, :tgt, 'entity', 'entity', :rel, 0.95, '{"source": "merge"}')
            """), {
                "id": str(uuid.uuid4()),
                "src": str(mkt_row.id),
                "tgt": str(ntangible_id),
                "rel": relation,
            })

    # Step 10: Import knowledge nodes
    ae.execute("""
        SELECT id, kind, title, content, primary_topic_key, confidence, trust_score,
               status, valid_from, valid_until, version, superseded_by, is_latest,
               is_core, recency_score, extraction_run_id, metadata
        FROM knowledge_nodes
        WHERE status = 'active' AND is_latest = true
    """)
    ae_knowledge = ae.fetchall()
    knowledge_count = 0
    for kn in ae_knowledge:
        existing = db.execute(text("SELECT id FROM knowledge_nodes WHERE id = :id"), {"id": str(kn["id"])}).fetchone()
        if existing:
            continue
        meta = _ensure_dict(kn["metadata"])
        meta["source"] = "agent_engine"
        if kn["is_core"]:
            meta["is_core"] = True
        if kn["recency_score"]:
            meta["recency_score"] = kn["recency_score"]
        superseded = kn["superseded_by"]
        if superseded:
            superseded = str(superseded)
        db.execute(text("""
            INSERT INTO knowledge_nodes (id, kind, title, content, primary_topic_key,
                confidence, trust_score, status, valid_from, valid_until,
                version, superseded_by, is_latest, metadata)
            VALUES (:id, :kind, :title, :content, :ptk,
                :confidence, :trust_score, :status, :valid_from, :valid_until,
                :version, :superseded_by, :is_latest, :metadata)
        """), {
            "id": str(kn["id"]),
            "kind": kn["kind"],
            "title": kn["title"],
            "content": kn["content"],
            "ptk": kn["primary_topic_key"],
            "confidence": kn["confidence"],
            "trust_score": kn["trust_score"],
            "status": kn["status"],
            "valid_from": kn["valid_from"],
            "valid_until": kn["valid_until"],
            "version": kn["version"],
            "superseded_by": superseded,
            "is_latest": kn["is_latest"],
            "metadata": psycopg2.extras.Json(meta),
        })
        knowledge_count += 1
    print(f"Imported {knowledge_count} knowledge nodes.")

    # Step 11: Import entity edges
    ae.execute("SELECT id, from_entity_id, to_entity_id, relation, confidence, status, valid_from, valid_until, metadata FROM entity_edges")
    ae_entity_edges = ae.fetchall()
    edge_count = 0
    for edge in ae_entity_edges:
        src = resolve(edge["from_entity_id"])
        tgt = resolve(edge["to_entity_id"])
        src_exists = db.execute(text("SELECT 1 FROM entity_nodes WHERE id = :id"), {"id": str(src)}).fetchone()
        tgt_exists = db.execute(text("SELECT 1 FROM entity_nodes WHERE id = :id"), {"id": str(tgt)}).fetchone()
        if not src_exists or not tgt_exists:
            continue
        meta = _ensure_dict(edge["metadata"])
        meta["source"] = "agent_engine"
        if edge["valid_from"]:
            meta["valid_from"] = edge["valid_from"].isoformat()
        if edge["valid_until"]:
            meta["valid_until"] = edge["valid_until"].isoformat()
        if edge["status"]:
            meta["ae_status"] = edge["status"]
        db.execute(text("""
            INSERT INTO entity_edges (id, source_id, target_id, source_type, target_type, relation, confidence, metadata)
            VALUES (:id, :src, :tgt, 'entity', 'entity', :rel, :conf, :meta)
        """), {
            "id": str(uuid.uuid4()),
            "src": str(src),
            "tgt": str(tgt),
            "rel": edge["relation"][:64],
            "conf": edge["confidence"],
            "meta": psycopg2.extras.Json(meta),
        })
        edge_count += 1
    print(f"Imported {edge_count} entity edges.")

    # Step 12: Import knowledge edges
    ae.execute("SELECT id, from_knowledge_id, to_knowledge_id, relation, confidence, metadata FROM knowledge_edges")
    ae_knowledge_edges = ae.fetchall()
    ke_count = 0
    for edge in ae_knowledge_edges:
        src_id = str(edge["from_knowledge_id"])
        tgt_id = str(edge["to_knowledge_id"])
        src_exists = db.execute(text("SELECT 1 FROM knowledge_nodes WHERE id = :id"), {"id": src_id}).fetchone()
        tgt_exists = db.execute(text("SELECT 1 FROM knowledge_nodes WHERE id = :id"), {"id": tgt_id}).fetchone()
        if not src_exists or not tgt_exists:
            continue
        meta = _ensure_dict(edge["metadata"])
        meta["source"] = "agent_engine"
        db.execute(text("""
            INSERT INTO knowledge_edges (id, source_id, target_id, relation, confidence, metadata)
            VALUES (:id, :src, :tgt, :rel, :conf, :meta)
        """), {
            "id": str(uuid.uuid4()),
            "src": src_id,
            "tgt": tgt_id,
            "rel": edge["relation"][:64],
            "conf": edge["confidence"],
            "meta": psycopg2.extras.Json(meta),
        })
        ke_count += 1
    print(f"Imported {ke_count} knowledge edges.")

    # Step 13: Rewrite metadata entity ID references
    id_remap_str = {}
    for old_id, new_id in {**ae_id_remap, **cross_remap}.items():
        id_remap_str[str(old_id)] = str(new_id)

    if id_remap_str:
        for table in ["knowledge_nodes", "entity_nodes"]:
            rows = db.execute(text(f"SELECT id, metadata FROM {table}")).fetchall()
            for row in rows:
                meta = row.metadata
                if not isinstance(meta, dict):
                    continue
                changed = False
                new_meta = dict(meta)
                for key, val in meta.items():
                    if isinstance(val, str) and val in id_remap_str:
                        new_meta[key] = id_remap_str[val]
                        changed = True
                if changed:
                    db.execute(text(f"UPDATE {table} SET metadata = :meta WHERE id = :id"), {
                        "meta": psycopg2.extras.Json(new_meta),
                        "id": str(row.id),
                    })
        print("Metadata entity ID references rewritten.")

    # Step 14: Add topic profiles
    existing_topics = {r.topic_key for r in db.execute(text("SELECT topic_key FROM topic_profiles")).fetchall()}
    for topic_key, display_name, desc in [
        ("work", "Work", "Work threads, companies, and professional context."),
        ("people", "People", "Relationships, contacts, and who matters."),
        ("projects", "Projects", "Current initiatives, deliverables, and project state."),
        ("finance", "Finance", "Financial items."),
    ]:
        if topic_key not in existing_topics:
            db.execute(text("""
                INSERT INTO topic_profiles (id, topic_key, display_name, description, enabled, priority)
                VALUES (:id, :key, :name, :desc, true, 'high')
            """), {"id": str(uuid.uuid4()), "key": topic_key, "name": display_name, "desc": desc})
    if "marketing" not in existing_topics:
        db.execute(text("""
            INSERT INTO topic_profiles (id, topic_key, display_name, description, enabled, priority)
            VALUES (:id, 'marketing', 'Marketing', 'Marketing content engine.', true, 'critical')
        """), {"id": str(uuid.uuid4())})
    print("Topic profiles ensured.")


if __name__ == "__main__":
    main()
