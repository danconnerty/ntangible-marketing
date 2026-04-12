# Brain Merge: Agent-Engine into NTangible Marketing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import agent-engine brain data (entities, knowledge, edges) into the ntangible_marketing database and wire up the app so the imported data is visible in the graph and available during content generation.

**Architecture:** One-time migration script reads from the agent-engine PostgreSQL database, deduplicates entities, and inserts into the ntangible_marketing database. Three app code changes: (1) add brain_facts retrieval channel to MemoryRetrievalService, (2) add topic_key parameter to graph queries, (3) add topic switcher to graph template.

**Tech Stack:** Python 3.13, SQLAlchemy, psycopg2, pytest, Jinja2, D3.js

**Spec:** `docs/superpowers/specs/2026-04-10-brain-merge-agent-engine-design.md`

---

### Task 1: Migration script — dedup map and entity filtering

**Files:**
- Create: `scripts/merge_agent_engine.py`

- [ ] **Step 1: Create the migration script with connection setup and dedup constants**

```python
#!/usr/bin/env python3
"""One-time migration: import agent-engine brain into ntangible_marketing."""

import re
import uuid
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from sqlalchemy import text

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
    # name -> agent-engine entity row
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
                # Also remap any internal dupes that pointed here
                for dupe_id, canon_id in ae_id_remap.items():
                    if canon_id == ae_row["id"]:
                        cross_remap[dupe_id] = mkt_row.id

    # Combined remap: agent-engine ID -> final ID in marketing DB
    def resolve(ae_id):
        # First resolve internal dedup, then cross-DB
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

    # Step 7: Import non-overlapping entities
    imported_count = 0
    for eid, row in import_entities.items():
        final_id = resolve(eid)
        if final_id != eid:
            continue  # This entity maps to an existing marketing node
        # Check not already in marketing DB
        existing = db.execute(text("SELECT id FROM entity_nodes WHERE id = :id"), {"id": str(eid)}).fetchone()
        if existing:
            continue
        meta = row["metadata"] or {}
        meta["source"] = "agent_engine"
        db.execute(text("""
            INSERT INTO entity_nodes (id, entity_type, canonical_name, slug, description, status, primary_topic_key, metadata)
            VALUES (:id, :entity_type, :canonical_name, :slug, :description, :status, NULL, :metadata)
        """), {
            "id": str(eid),
            "entity_type": row["entity_type"],
            "canonical_name": row["canonical_name"],
            "slug": slugify(row["canonical_name"]),
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
        ae_meta = ae_row["metadata"] or {}
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
        # Check edge doesn't already exist
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
        meta = kn["metadata"] or {}
        meta["source"] = "agent_engine"
        if kn["is_core"]:
            meta["is_core"] = True
        if kn["recency_score"]:
            meta["recency_score"] = kn["recency_score"]
        superseded = kn["superseded_by"]
        if superseded:
            # Remap through dedup if needed (knowledge nodes don't dedup, but just in case)
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
        # Skip if either endpoint was filtered out
        src_exists = (str(src) in {str(e) for e in import_entities}) or db.execute(text("SELECT 1 FROM entity_nodes WHERE id = :id"), {"id": str(src)}).fetchone()
        tgt_exists = (str(tgt) in {str(e) for e in import_entities}) or db.execute(text("SELECT 1 FROM entity_nodes WHERE id = :id"), {"id": str(tgt)}).fetchone()
        if not src_exists or not tgt_exists:
            continue
        meta = edge["metadata"] or {}
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
            "rel": edge["relation"],
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
        # Both endpoints must exist in marketing DB
        src_exists = db.execute(text("SELECT 1 FROM knowledge_nodes WHERE id = :id"), {"id": src_id}).fetchone()
        tgt_exists = db.execute(text("SELECT 1 FROM knowledge_nodes WHERE id = :id"), {"id": tgt_id}).fetchone()
        if not src_exists or not tgt_exists:
            continue
        meta = edge["metadata"] or {}
        meta["source"] = "agent_engine"
        db.execute(text("""
            INSERT INTO knowledge_edges (id, source_id, target_id, relation, confidence, metadata)
            VALUES (:id, :src, :tgt, :rel, :conf, :meta)
        """), {
            "id": str(uuid.uuid4()),
            "src": src_id,
            "tgt": tgt_id,
            "rel": edge["relation"],
            "conf": edge["confidence"],
            "meta": psycopg2.extras.Json(meta),
        })
        ke_count += 1
    print(f"Imported {ke_count} knowledge edges.")

    # Step 13: Rewrite metadata entity ID references
    # Scan knowledge_nodes and entity_nodes metadata for UUIDs that need remapping
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
```

- [ ] **Step 2: Run the migration script**

```bash
cd /Users/elliot18/Desktop/Home/Projects/ntangible_marketing
.venv/bin/python3 scripts/merge_agent_engine.py
```

Expected output:
```
Entities to import: ~120 (filtered from 488)
Imported ~120 new entity nodes.
Imported ~410 knowledge nodes.
Imported ~200 entity edges.
Imported ~300 knowledge edges.
Metadata entity ID references rewritten.
Topic profiles ensured.
Migration committed successfully.
```

- [ ] **Step 3: Verify the migration**

```bash
.venv/bin/python3 -c "
from app.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
for table in ['entity_nodes', 'knowledge_nodes', 'entity_edges', 'knowledge_edges', 'topic_profiles']:
    count = db.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()
    print(f'{table}: {count}')
# Check agent_engine sourced data
ae_entities = db.execute(text(\"SELECT COUNT(*) FROM entity_nodes WHERE metadata->>'source' = 'agent_engine'\")).scalar()
print(f'Agent-engine entities: {ae_entities}')
ae_knowledge = db.execute(text(\"SELECT COUNT(*) FROM knowledge_nodes WHERE metadata->>'source' = 'agent_engine'\")).scalar()
print(f'Agent-engine knowledge: {ae_knowledge}')
# Check role edges exist
role_edges = db.execute(text(\"SELECT relation, COUNT(*) FROM entity_edges WHERE relation IN ('partner_of','client_of','competes_with') GROUP BY relation\")).fetchall()
for r in role_edges:
    print(f'  {r[0]}: {r[1]}')
db.close()
"
```

Expected: entity_nodes > 140, knowledge_nodes > 440, role edges for partner_of, client_of, competes_with.

- [ ] **Step 4: Commit**

```bash
git add scripts/merge_agent_engine.py
git commit -m "feat: add agent-engine brain merge migration script"
```

---

### Task 2: Add brain_facts retrieval channel to MemoryRetrievalService

**Files:**
- Modify: `app/services/memory_retrieval.py:277-314`
- Test: `tests/test_memory_retrieval.py`

- [ ] **Step 1: Write the failing test for _search_brain_facts**

Add to `tests/test_memory_retrieval.py`:

```python
def _fact_node(*, title="NTangible fact", content="Dan Connerty is CEO of NTangible", topic="work"):
    return KnowledgeNode(
        id=uuid.uuid4(),
        kind="fact",
        title=title,
        content=content,
        status="active",
        metadata_={"source": "agent_engine", "search_text": f"{title} {content}"},
        created_at=datetime.now(timezone.utc),
    )


def test_search_brain_facts_returns_matching_facts():
    service = MemoryRetrievalService(MagicMock())
    fact1 = _fact_node(title="Dan Connerty Is CEO", content="Dan Connerty founded NTangible.")
    fact2 = _fact_node(title="Vercel Hosting", content="NTangible is hosted on Vercel hobby plan.")
    service.bq = MagicMock()
    service.bq.list_knowledge_by_kind = MagicMock(return_value=[fact1, fact2])

    results = service._search_brain_facts(query="Dan Connerty NTangible", limit=5)

    assert len(results) >= 1
    assert results[0]["id"] == str(fact1.id)
    assert results[0]["title"] == "Dan Connerty Is CEO"


def test_search_brain_facts_not_filtered_by_platform_or_bucket():
    """Facts should be returned regardless of platform or status."""
    service = MemoryRetrievalService(MagicMock())
    fact = _fact_node(title="Alliance Partnership", content="Alliance Fastpitch partnered with NTangible.")
    service.bq = MagicMock()
    service.bq.list_knowledge_by_kind = MagicMock(return_value=[fact])

    results = service._search_brain_facts(query="Alliance partnership", limit=5)

    assert len(results) == 1


def test_build_generation_context_includes_brain_facts():
    service = MemoryRetrievalService(MagicMock())
    fact = _fact_node()
    approved = _knowledge_node(status="approved")
    rejected = _knowledge_node(status="rejected")

    service._load_candidate_items = MagicMock(return_value=[approved, rejected])
    service.bq = MagicMock()
    service.bq.list_knowledge_by_kind = MagicMock(return_value=[fact])

    result = service.build_generation_context(
        query="NTangible",
        platform=Platform.LINKEDIN,
        workflow_slug="linkedin-thought-leadership",
    )

    assert "brain_facts" in result
    assert "approved_examples" in result
    assert "rejected_examples" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python3 -m pytest tests/test_memory_retrieval.py -v -k "brain_facts"
```

Expected: FAIL — `_search_brain_facts` does not exist, `brain_facts` not in result.

- [ ] **Step 3: Implement _search_brain_facts and update build_generation_context**

In `app/services/memory_retrieval.py`, add the `_search_brain_facts` method after `_load_candidate_items` (line 314):

```python
    def _search_brain_facts(self, *, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search fact nodes by keyword relevance. No bucket/platform filtering."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        facts = self.bq.list_knowledge_by_kind("fact", limit=250)
        scored: list[tuple[float, KnowledgeNode]] = []
        for item in facts:
            score = self._score_item(item, query_tokens, None, None, None)
            if score > 0:
                scored.append((score, item))
        scored.sort(
            key=lambda value: (
                value[0],
                value[1].created_at,
            ),
            reverse=True,
        )
        return [self._serialize_item(item, score) for score, item in scored[:limit]]
```

Update `build_generation_context` (line 277) — add `facts_limit` parameter and `brain_facts` channel:

Replace the existing method with:

```python
    def build_generation_context(
        self,
        *,
        query: str,
        platform: Platform,
        workflow_slug: str | None = None,
        approved_limit: int = 5,
        rejected_limit: int = 2,
        facts_limit: int = 5,
    ) -> dict[str, Any]:
        # Use string "approved"/"rejected" as bucket values
        approved = self.search(
            query=query,
            platform=platform,
            bucket=_BucketCompat("approved"),
            workflow_slug=workflow_slug,
            limit=approved_limit,
        )
        rejected = self.search(
            query=query,
            platform=platform,
            bucket=_BucketCompat("rejected"),
            workflow_slug=workflow_slug,
            limit=rejected_limit,
        )
        brain_facts = self._search_brain_facts(query=query, limit=facts_limit)
        memory_ids = [item["id"] for item in approved + rejected + brain_facts]
        return {
            "approved_examples": approved,
            "rejected_examples": rejected,
            "brain_facts": brain_facts,
            "memory_ids": memory_ids,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python3 -m pytest tests/test_memory_retrieval.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/memory_retrieval.py tests/test_memory_retrieval.py
git commit -m "feat: add brain_facts retrieval channel to MemoryRetrievalService"
```

---

### Task 3: Wire brain_facts into prompt assembly

**Files:**
- Modify: `app/services/prompt_assembler.py:65-107`

- [ ] **Step 1: Add _facts_block helper and wire into assemble method**

In `app/services/prompt_assembler.py`, add a `_facts_block` method (after `_examples_block`):

```python
    def _facts_block(self, facts: list[dict[str, Any]]) -> str:
        if not facts:
            return ""
        lines = ["Company context (factual grounding — use as background, not as content to imitate):"]
        for fact in facts:
            lines.append(f"- {fact['title']}: {fact['content'][:300]}")
        return "\n".join(lines)
```

Then update the `assemble` method. After line 73 (the `rejected_text` assignment), add:

```python
        facts_text = self._facts_block(retrieval.get("brain_facts", []))
```

And add `facts_text` to the system prompt assembly (inside the `"\n\n".join(...)` list, after the `_blog_context_text` line):

```python
                facts_text,
```

- [ ] **Step 2: Run existing tests to verify nothing is broken**

```bash
.venv/bin/python3 -m pytest tests/ -v -k "prompt_assembler or memory_retrieval" --timeout=30
```

Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add app/services/prompt_assembler.py
git commit -m "feat: include brain facts as company context in prompt assembly"
```

---

### Task 4: Add topic_key parameter to BrainQuery.get_graph_data

**Files:**
- Modify: `app/services/brain_query.py:362-413`
- Test: `tests/test_brain_query.py`

- [ ] **Step 1: Write the failing test for topic_key=None**

Add to `tests/test_brain_query.py`:

```python
def test_get_graph_data_topic_none_returns_all(db, bq):
    """topic_key=None should return all entities and knowledge regardless of topic."""
    e1 = bq.create_entity(entity_type="company", canonical_name="Acme", slug="acme", metadata={"primary_topic_key": None})
    db.flush()
    # Manually set topic
    from sqlalchemy import text
    db.execute(text("UPDATE entity_nodes SET primary_topic_key = NULL WHERE id = :id"), {"id": str(e1.id)})

    e2 = bq.create_entity(entity_type="workflow", canonical_name="WF1", slug="wf1")
    db.flush()
    db.execute(text("UPDATE entity_nodes SET primary_topic_key = 'marketing' WHERE id = :id"), {"id": str(e2.id)})

    k1 = bq.create_knowledge_node(kind="fact", title="Fact1", content="test", status="active")
    db.flush()
    db.execute(text("UPDATE knowledge_nodes SET primary_topic_key = 'work' WHERE id = :id"), {"id": str(k1.id)})

    db.flush()

    data = bq.get_graph_data(topic_key=None)
    entity_ids = {e.id for e in data["entities"]}
    knowledge_ids = {k.id for k in data["knowledge"]}

    assert e1.id in entity_ids
    assert e2.id in entity_ids
    assert k1.id in knowledge_ids
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python3 -m pytest tests/test_brain_query.py -v -k "topic_none"
```

Expected: FAIL — currently `get_graph_data` filters by `== topic_key` which matches nothing when None (or matches all NULLs).

- [ ] **Step 3: Update get_graph_data to support topic_key=None**

In `app/services/brain_query.py`, replace the `get_graph_data` method (line 362-413):

```python
    def get_graph_data(self, *, topic_key: str | None = "marketing") -> dict:
        """Return a dict of all brain data filtered to *topic_key*.

        When *topic_key* is ``None`` all nodes are returned (full brain view).
        Topic-specific views only show nodes explicitly tagged with that topic.

        Structure::

            {
                "entities": [EntityNode, ...],
                "knowledge": [KnowledgeNode, ...],
                "entity_edges": [EntityEdge, ...],
                "knowledge_edges": [KnowledgeEdge, ...],
            }
        """
        if topic_key is None:
            entities = self.db.query(EntityNode).all()
            knowledge = (
                self.db.query(KnowledgeNode)
                .filter(KnowledgeNode.is_latest == True)  # noqa: E712
                .all()
            )
        else:
            entities = (
                self.db.query(EntityNode)
                .filter(EntityNode.primary_topic_key == topic_key)
                .all()
            )
            knowledge = (
                self.db.query(KnowledgeNode)
                .filter(KnowledgeNode.primary_topic_key == topic_key)
                .all()
            )

        entity_ids = {e.id for e in entities}
        knowledge_ids = {k.id for k in knowledge}
        all_node_ids = entity_ids | knowledge_ids

        entity_edges = (
            self.db.query(EntityEdge)
            .filter(
                EntityEdge.source_id.in_(all_node_ids)
                | EntityEdge.target_id.in_(all_node_ids)
            )
            .all()
            if all_node_ids
            else []
        )

        knowledge_edges = (
            self.db.query(KnowledgeEdge)
            .filter(
                KnowledgeEdge.source_id.in_(knowledge_ids)
                | KnowledgeEdge.target_id.in_(knowledge_ids)
            )
            .all()
            if knowledge_ids
            else []
        )

        return {
            "entities": entities,
            "knowledge": knowledge,
            "entity_edges": entity_edges,
            "knowledge_edges": knowledge_edges,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python3 -m pytest tests/test_brain_query.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/brain_query.py tests/test_brain_query.py
git commit -m "feat: support topic_key=None in get_graph_data for full brain view"
```

---

### Task 5: Add topic parameter to graph routes

**Files:**
- Modify: `app/web/routes.py:4004-4084`

- [ ] **Step 1: Update graph_view, graph_data, and brain_graph_view routes**

In `app/web/routes.py`, update the three graph routes:

Replace `graph_view` (line 4004-4019):

```python
@web_router.get("/graph", response_class=HTMLResponse)
def graph_view(request: Request, topic: str = "marketing", db: Session = Depends(get_db)):
    effective_topic = None if topic == "all" else topic
    data = BrainQuery(db).get_graph_data(topic_key=effective_topic)
    nodes = (
        [{"id": str(e.id), "label": e.canonical_name, "group": "entity", "type": e.entity_type} for e in data["entities"]]
        + [{"id": str(k.id), "label": k.title, "group": "knowledge", "type": k.kind} for k in data["knowledge"]]
    )
    links = (
        [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["entity_edges"]]
        + [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["knowledge_edges"]]
    )
    topics = db.query(TopicProfile).filter(TopicProfile.enabled == True).order_by(TopicProfile.priority.asc()).all()  # noqa: E712
    return templates.TemplateResponse(request, "graph.html", {
        "request": request,
        "nodes_json": json.dumps(nodes),
        "links_json": json.dumps(links),
        "current_topic": topic,
        "topics": topics,
    })
```

Replace `graph_data` (line 4022-4030):

```python
@web_router.get("/graph/data")
def graph_data(topic: str = "marketing", db: Session = Depends(get_db)):
    effective_topic = None if topic == "all" else topic
    data = BrainQuery(db).get_graph_data(topic_key=effective_topic)
    return {
        "entities": [{"id": str(e.id), "type": e.entity_type, "label": e.canonical_name, "status": e.status} for e in data["entities"]],
        "knowledge": [{"id": str(k.id), "type": k.kind, "label": k.title, "status": k.status} for k in data["knowledge"]],
        "entity_edges": [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["entity_edges"]],
        "knowledge_edges": [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["knowledge_edges"]],
    }
```

Replace `brain_graph_view` (line 4067-4084):

```python
@web_router.get("/brain/graph", response_class=HTMLResponse)
def brain_graph_view(request: Request, topic: str = "marketing", db: Session = Depends(get_db)):
    effective_topic = None if topic == "all" else topic
    data = BrainQuery(db).get_graph_data(topic_key=effective_topic)
    nodes = (
        [{"id": str(e.id), "label": e.canonical_name, "group": "entity", "type": e.entity_type, "description": e.description or ""} for e in data["entities"]]
        + [{"id": str(k.id), "label": k.title, "group": "knowledge", "type": k.kind, "content": (k.content or "")[:400], "confidence": k.confidence, "trust_score": k.trust_score} for k in data["knowledge"]]
    )
    links = (
        [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["entity_edges"]]
        + [{"source": str(e.source_id), "target": str(e.target_id), "relation": e.relation} for e in data["knowledge_edges"]]
    )
    topics = db.query(TopicProfile).filter(TopicProfile.enabled == True).order_by(TopicProfile.priority.asc()).all()  # noqa: E712
    return templates.TemplateResponse(request, "graph.html", {
        "request": request,
        "page": "brain_graph",
        "nodes_json": json.dumps(nodes),
        "links_json": json.dumps(links),
        "current_topic": topic,
        "topics": topics,
        "sidebar_topics": _brain_sidebar_topics(db),
    })
```

- [ ] **Step 2: Verify the import for TopicProfile is present**

Check that `TopicProfile` is imported at the top of `routes.py`. If not, add it to the existing brain model imports:

```python
from app.models.brain import EntityNode, KnowledgeNode, EntityEdge, KnowledgeEdge, TopicProfile
```

- [ ] **Step 3: Run existing route tests**

```bash
.venv/bin/python3 -m pytest tests/test_web_brain_and_analytics_view.py -v --timeout=30
```

Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add app/web/routes.py
git commit -m "feat: add topic query parameter to graph routes"
```

---

### Task 6: Rebuild graph template with full brain UI

**Files:**
- Rewrite: `app/web/templates/graph.html`

The graph template needs to support the merged brain: expanded entity type colors (person, company, org, product, place, topic alongside the marketing types), a topic switcher, dynamic legend, node/edge count stats, and NTangible as the visual center of the graph. The existing interactive features (drag, zoom, click, search, layer filters, detail panel, hover effects) are kept and enhanced.

- [ ] **Step 1: Rewrite graph.html with full brain UI**

Replace the entire `graph.html` with the updated template. Key changes from current:

1. **Topic switcher** — dropdown in header, reloads page with `?topic=` param
2. **Expanded color palette** — adds person (#3b82f6), company (#22c55e), org (#10b981), product (#f97316), place (#8b5cf6), topic (#eab308) alongside existing marketing colors
3. **Dynamic legend** — built from actual node types in the data, not hardcoded
4. **Node/edge stats** — live count display like agent-engine
5. **Center NTangible** — if an entity named "NTangible" exists, pin it to the center at start
6. **Knowledge kind colors** — expanded for fact (#06b6d4), event (#a855f7), task (#f59e0b), deadline (#ef4444), preference (#ec4899) alongside existing draft/claim/reference colors

```html
{% extends "base.html" %}

{% block content %}
<header class="page-header" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
  <div>
    <h1>Knowledge Graph</h1>
    <p class="subtitle">Force-directed view of entities and their relationships.</p>
  </div>
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
    {% if topics is defined %}
    <select id="topic-select" onchange="window.location.search='?topic='+this.value"
      style="padding:5px 10px;font-size:12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--foreground);cursor:pointer;">
      {% for t in topics %}
      <option value="{{ t.topic_key }}" {% if current_topic == t.topic_key %}selected{% endif %}>{{ t.display_name }}</option>
      {% endfor %}
      <option value="all" {% if current_topic == 'all' %}selected{% endif %}>All</option>
    </select>
    {% endif %}
    <input id="graph-search" type="text" placeholder="Search nodes..."
      style="padding:5px 12px;font-size:12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--foreground);width:180px;">
    <div style="display:flex;gap:4px;">
      <button class="layer-btn active" data-layer="all"
        style="padding:4px 12px;font-size:12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--foreground);cursor:pointer;">All</button>
      <button class="layer-btn" data-layer="entity"
        style="padding:4px 12px;font-size:12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--muted-foreground);cursor:pointer;">Entities</button>
      <button class="layer-btn" data-layer="knowledge"
        style="padding:4px 12px;font-size:12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--muted-foreground);cursor:pointer;">Knowledge</button>
    </div>
    <span id="graph-stats" style="font-size:11px;color:var(--muted-foreground);font-variant-numeric:tabular-nums;"></span>
  </div>
</header>

<div style="display:flex;gap:0;position:relative;">
  <div class="card" style="padding:0;overflow:hidden;flex:1;position:relative;">
    <div id="graph-container" style="width:100%;height:680px;background:var(--card);border:1px solid var(--border);border-radius:8px;"></div>
  </div>

  <div id="detail-panel" style="
    display:none;
    width:320px;
    min-width:320px;
    background:var(--card);
    border:1px solid var(--border);
    border-radius:8px;
    margin-left:12px;
    padding:20px;
    overflow-y:auto;
    max-height:680px;
  ">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h3 id="detail-title" style="margin:0;font-size:16px;color:var(--foreground);"></h3>
      <button id="detail-close" style="background:none;border:none;color:var(--muted-foreground);cursor:pointer;font-size:18px;padding:0 4px;">&times;</button>
    </div>
    <div id="detail-badge" style="margin-bottom:12px;"></div>
    <div id="detail-body" style="font-size:13px;color:var(--muted-foreground);line-height:1.6;"></div>
  </div>
</div>

<div id="graph-legend" style="display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;"></div>

<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script>
(function () {
  var nodes = {{ nodes_json | safe }};
  var links = {{ links_json | safe }};

  // -- Color maps (agent-engine + marketing entity types) --
  var entityColors = {
    person: "#3b82f6",
    company: "#22c55e",
    org: "#10b981",
    product: "#f97316",
    place: "#8b5cf6",
    topic: "#eab308",
    workflow: "#3b82f6",
    partner: "#22c55e",
    client: "#10b981",
    competitor: "#f97316",
    publishing_channel: "#8b5cf6",
    content_pillar: "#eab308"
  };
  var knowledgeColors = {
    draft: "#f43f5e",
    approved_claim: "#14b8a6",
    reference_content: "#64748b",
    schedule_rule: "#eab308",
    observation: "#f97316",
    review_action: "#a855f7",
    fact: "#06b6d4",
    event: "#a855f7",
    task: "#f59e0b",
    deadline: "#ef4444",
    preference: "#ec4899"
  };

  function nodeColor(d) {
    if (d.group === "entity") return entityColors[d.type] || "#3b82f6";
    return knowledgeColors[d.type] || "#f43f5e";
  }

  // -- Connection counts for sizing --
  var linkCount = {};
  links.forEach(function(l) {
    linkCount[l.source] = (linkCount[l.source] || 0) + 1;
    linkCount[l.target] = (linkCount[l.target] || 0) + 1;
  });
  var maxLinks = Math.max(1, d3.max(Object.values(linkCount)) || 1);

  function nodeRadius(d) {
    var count = linkCount[d.id] || 0;
    return 4 + (count / maxLinks) * 10;
  }

  // -- Build dynamic legend from actual data --
  var legendEl = document.getElementById("graph-legend");
  var seenTypes = {};
  nodes.forEach(function(n) {
    var key = n.group + ":" + n.type;
    if (!seenTypes[key]) {
      seenTypes[key] = { group: n.group, type: n.type, color: nodeColor(n) };
    }
  });
  Object.values(seenTypes).sort(function(a, b) {
    if (a.group !== b.group) return a.group === "entity" ? -1 : 1;
    return a.type.localeCompare(b.type);
  }).forEach(function(t) {
    var shape = t.group === "knowledge"
      ? '<svg width="14" height="14"><rect x="2" y="2" width="10" height="10" transform="rotate(45 7 7)" fill="' + t.color + '" opacity="0.85"/></svg>'
      : '<svg width="14" height="14"><circle cx="7" cy="7" r="6" fill="' + t.color + '" opacity="0.85"/></svg>';
    var item = document.createElement("div");
    item.className = "card";
    item.style.cssText = "display:flex;align-items:center;gap:8px;padding:6px 10px;cursor:pointer;";
    item.innerHTML = shape + '<span class="text-muted" style="font-size:11px;">' + t.type.replace(/_/g, " ") + '</span>';
    legendEl.appendChild(item);
  });

  // -- Stats --
  document.getElementById("graph-stats").textContent = nodes.length + " nodes, " + links.length + " edges";

  // -- Container setup --
  var container = document.getElementById("graph-container");
  var width  = container.clientWidth  || 900;
  var height = container.clientHeight || 680;

  var svg = d3.select("#graph-container")
    .append("svg")
    .attr("width", width)
    .attr("height", height);

  var g = svg.append("g");
  svg.call(d3.zoom().scaleExtent([0.1, 8]).on("zoom", function(event) {
    g.attr("transform", event.transform);
  }));

  // Arrow marker
  svg.append("defs").append("marker")
    .attr("id", "arrow")
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 18)
    .attr("refY", 0)
    .attr("markerWidth", 6)
    .attr("markerHeight", 6)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "#6b7280");

  // -- Pin NTangible to center if it exists --
  var ntangibleNode = nodes.find(function(n) {
    return n.group === "entity" && (n.label === "NTangible" || n.label === "NTangible Inc.");
  });
  if (ntangibleNode) {
    ntangibleNode.fx = width / 2;
    ntangibleNode.fy = height / 2;
    // Release after warmup
    setTimeout(function() { ntangibleNode.fx = null; ntangibleNode.fy = null; }, 4000);
  }

  // -- Simulation --
  var simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(function(d) { return d.id; }).distance(80).strength(0.5))
    .force("charge", d3.forceManyBody().strength(-150))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collide", d3.forceCollide(20));

  // -- Links --
  var link = g.append("g")
    .attr("stroke", "#374151")
    .attr("stroke-opacity", 0.4)
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("stroke-width", 1.2)
    .attr("marker-end", "url(#arrow)")
    .each(function(d) {
      var sourceNode = nodes.find(function(n) { return n.id === (d.source.id || d.source); });
      var targetNode = nodes.find(function(n) { return n.id === (d.target.id || d.target); });
      if ((sourceNode && sourceNode.group === "knowledge") || (targetNode && targetNode.group === "knowledge")) {
        d3.select(this).attr("stroke-dasharray", "4,3");
      }
    });

  // -- Link labels --
  var linkLabel = g.append("g")
    .selectAll("text")
    .data(links)
    .join("text")
    .attr("fill", "#6b7280")
    .attr("font-size", "8px")
    .attr("text-anchor", "middle")
    .attr("dy", -4)
    .text(function(d) { return d.relation || ""; });

  // -- Node groups --
  var node = g.append("g")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .call(
      d3.drag()
        .on("start", dragStarted)
        .on("drag", dragged)
        .on("end", dragEnded)
    )
    .on("click", function(event, d) {
      event.stopPropagation();
      selectNode(d);
    })
    .on("mouseover", function(event, d) {
      d3.select(this).select(".node-label").style("opacity", 1);
      highlightConnected(d);
    })
    .on("mouseout", function(event, d) {
      if (!selectedNode) {
        clearHighlight();
      }
      if (selectedNode !== d) {
        var count = linkCount[d.id] || 0;
        d3.select(this).select(".node-label").style("opacity", count >= 3 ? 0.85 : 0);
      }
    });

  // Entity nodes: circles
  node.filter(function(d) { return d.group !== "knowledge"; })
    .append("circle")
    .attr("class", "node-shape")
    .attr("r", function(d) { return nodeRadius(d); })
    .attr("fill", function(d) { return nodeColor(d); })
    .attr("fill-opacity", 0.85)
    .attr("stroke", function(d) { return d3.color(nodeColor(d)).brighter(0.6); })
    .attr("stroke-width", 1.5);

  // Knowledge nodes: diamonds
  node.filter(function(d) { return d.group === "knowledge"; })
    .append("rect")
    .attr("class", "node-shape")
    .attr("x", function(d) { return -nodeRadius(d); })
    .attr("y", function(d) { return -nodeRadius(d); })
    .attr("width", function(d) { return nodeRadius(d) * 2; })
    .attr("height", function(d) { return nodeRadius(d) * 2; })
    .attr("transform", "rotate(45)")
    .attr("fill", function(d) { return nodeColor(d); })
    .attr("fill-opacity", 0.85)
    .attr("stroke", function(d) { return d3.color(nodeColor(d)).brighter(0.6); })
    .attr("stroke-width", 1.5);

  // Labels
  node.append("text")
    .attr("class", "node-label")
    .attr("dy", function(d) { return nodeRadius(d) + 12; })
    .attr("text-anchor", "middle")
    .attr("fill", "var(--muted-foreground)")
    .attr("font-size", "10px")
    .attr("pointer-events", "none")
    .style("opacity", function(d) { return (linkCount[d.id] || 0) >= 3 ? 0.85 : 0; })
    .text(function(d) { return d.label || d.id; });

  // -- Tick --
  simulation.on("tick", function() {
    link
      .attr("x1", function(d) { return d.source.x; })
      .attr("y1", function(d) { return d.source.y; })
      .attr("x2", function(d) { return d.target.x; })
      .attr("y2", function(d) { return d.target.y; });
    linkLabel
      .attr("x", function(d) { return (d.source.x + d.target.x) / 2; })
      .attr("y", function(d) { return (d.source.y + d.target.y) / 2; });
    node.attr("transform", function(d) {
      return "translate(" + d.x + "," + d.y + ")";
    });
  });

  // -- Drag --
  function dragStarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x; d.fy = d.y;
  }
  function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
  function dragEnded(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null; d.fy = null;
  }

  // -- Highlight connected on hover --
  function highlightConnected(d) {
    var connectedIds = new Set([d.id]);
    links.forEach(function(l) {
      var sid = l.source.id || l.source;
      var tid = l.target.id || l.target;
      if (sid === d.id) connectedIds.add(tid);
      if (tid === d.id) connectedIds.add(sid);
    });
    node.style("opacity", function(n) { return connectedIds.has(n.id) ? 1 : 0.08; });
    link.style("opacity", function(l) {
      var sid = l.source.id || l.source;
      var tid = l.target.id || l.target;
      return (sid === d.id || tid === d.id) ? 0.8 : 0.03;
    });
    linkLabel.style("opacity", function(l) {
      var sid = l.source.id || l.source;
      var tid = l.target.id || l.target;
      return (sid === d.id || tid === d.id) ? 1 : 0;
    });
  }

  function clearHighlight() {
    node.style("opacity", function(d) { return d3.select(this).style("display") === "none" ? 0 : 1; });
    link.style("opacity", 0.4);
    linkLabel.style("opacity", 1);
  }

  // -- Selection --
  var selectedNode = null;

  function selectNode(d) {
    selectedNode = d;
    highlightConnected(d);
    node.select(".node-label").style("opacity", function(n) {
      var connectedIds = new Set([d.id]);
      links.forEach(function(l) {
        var sid = l.source.id || l.source;
        var tid = l.target.id || l.target;
        if (sid === d.id) connectedIds.add(tid);
        if (tid === d.id) connectedIds.add(sid);
      });
      return connectedIds.has(n.id) ? 1 : 0;
    });
    showDetail(d);
  }

  function clearSelection() {
    selectedNode = null;
    clearHighlight();
    node.select(".node-label").style("opacity", function(d) {
      return (linkCount[d.id] || 0) >= 3 ? 0.85 : 0;
    });
    document.getElementById("detail-panel").style.display = "none";
  }

  svg.on("click", clearSelection);

  // -- Detail panel --
  function showDetail(d) {
    var panel = document.getElementById("detail-panel");
    var title = document.getElementById("detail-title");
    var badge = document.getElementById("detail-badge");
    var body  = document.getElementById("detail-body");
    panel.style.display = "block";
    title.textContent = d.label || d.id;

    var badgeColor = nodeColor(d);
    badge.innerHTML = '<span style="display:inline-block;padding:2px 10px;border-radius:9999px;font-size:11px;font-weight:600;background:' +
      badgeColor + '20;color:' + badgeColor + ';">' + (d.type || d.group) + '</span>';

    var html = "";
    if (d.group === "entity") {
      if (d.description) html += '<p style="margin:0 0 12px;">' + d.description + '</p>';
    } else {
      if (d.content) html += '<p style="margin:0 0 12px;">' + (d.content.length > 300 ? d.content.substring(0,300) + '...' : d.content) + '</p>';
      if (typeof d.confidence === "number") {
        var pct = Math.round(d.confidence * 100);
        var barColor = pct >= 80 ? "#22c55e" : pct >= 50 ? "#eab308" : "#ef4444";
        html += '<div style="margin-bottom:8px;"><span style="font-size:11px;color:var(--muted-foreground);">Confidence</span>';
        html += '<div style="width:100%;height:6px;border-radius:3px;background:var(--muted);margin-top:4px;">';
        html += '<div style="width:' + pct + '%;height:100%;border-radius:3px;background:' + barColor + ';"></div></div>';
        html += '<span style="font-size:11px;color:var(--muted-foreground);">' + pct + '%</span></div>';
      }
      if (typeof d.trust_score === "number") {
        var tpct = Math.round(d.trust_score * 100);
        var tColor = tpct >= 80 ? "#22c55e" : tpct >= 50 ? "#eab308" : "#ef4444";
        html += '<div style="margin-bottom:8px;"><span style="font-size:11px;color:var(--muted-foreground);">Trust</span>';
        html += '<div style="width:100%;height:6px;border-radius:3px;background:var(--muted);margin-top:4px;">';
        html += '<div style="width:' + tpct + '%;height:100%;border-radius:3px;background:' + tColor + ';"></div></div>';
        html += '<span style="font-size:11px;color:var(--muted-foreground);">' + tpct + '%</span></div>';
      }
    }

    // Connections list
    var connections = [];
    links.forEach(function(l) {
      var sid = l.source.id || l.source;
      var tid = l.target.id || l.target;
      if (sid === d.id) {
        var target = nodes.find(function(n) { return n.id === tid; });
        if (target) connections.push({ node: target, relation: l.relation, dir: "outgoing" });
      }
      if (tid === d.id) {
        var source = nodes.find(function(n) { return n.id === sid; });
        if (source) connections.push({ node: source, relation: l.relation, dir: "incoming" });
      }
    });

    if (connections.length > 0) {
      html += '<div style="margin-top:16px;border-top:1px solid var(--border);padding-top:12px;">';
      html += '<div style="font-size:12px;font-weight:600;color:var(--foreground);margin-bottom:8px;">Connections (' + connections.length + ')</div>';
      connections.forEach(function(c) {
        var color = nodeColor(c.node);
        var arrow = c.dir === "outgoing" ? " &rarr; " : " &larr; ";
        html += '<div style="display:flex;align-items:center;gap:6px;padding:4px 0;font-size:12px;cursor:pointer;" onclick="document.querySelector(\'[data-node-id=\\\'' + c.node.id + '\\\']\')&&document.querySelector(\'[data-node-id=\\\'' + c.node.id + '\\\']\').dispatchEvent(new Event(\'click\'))">';
        html += '<span style="display:inline-block;width:8px;height:8px;border-radius:' + (c.node.group === "knowledge" ? "0" : "50%") + ';background:' + color + ';' + (c.node.group === "knowledge" ? "transform:rotate(45deg);" : "") + '"></span>';
        html += '<span style="color:var(--foreground);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + (c.node.label || c.node.id) + '</span>';
        if (c.relation) html += '<span style="color:var(--muted-foreground);font-size:10px;white-space:nowrap;">' + c.relation + '</span>';
        html += '</div>';
      });
      html += '</div>';
    }

    body.innerHTML = html;
  }

  document.getElementById("detail-close").addEventListener("click", clearSelection);

  // -- Layer toggles --
  var currentLayer = "all";
  document.querySelectorAll(".layer-btn").forEach(function(btn) {
    btn.addEventListener("click", function() {
      currentLayer = btn.dataset.layer;
      document.querySelectorAll(".layer-btn").forEach(function(b) {
        b.classList.remove("active");
        b.style.color = "var(--muted-foreground)";
      });
      btn.classList.add("active");
      btn.style.color = "var(--foreground)";
      applyFilters();
    });
  });

  // -- Search --
  var searchInput = document.getElementById("graph-search");
  var searchTerm = "";
  searchInput.addEventListener("input", function() {
    searchTerm = this.value.toLowerCase().trim();
    applyFilters();
  });

  function applyFilters() {
    node.style("display", function(d) {
      if (currentLayer !== "all" && d.group !== currentLayer) return "none";
      return "block";
    });
    link.style("display", function(l) {
      var sn = typeof l.source === "object" ? l.source : nodes.find(function(n) { return n.id === l.source; });
      var tn = typeof l.target === "object" ? l.target : nodes.find(function(n) { return n.id === l.target; });
      if (!sn || !tn) return "none";
      if (currentLayer !== "all") {
        if (sn.group !== currentLayer || tn.group !== currentLayer) return "none";
      }
      return "block";
    });
    linkLabel.style("display", function(l) {
      var sn = typeof l.source === "object" ? l.source : nodes.find(function(n) { return n.id === l.source; });
      var tn = typeof l.target === "object" ? l.target : nodes.find(function(n) { return n.id === l.target; });
      if (!sn || !tn) return "none";
      if (currentLayer !== "all") {
        if (sn.group !== currentLayer || tn.group !== currentLayer) return "none";
      }
      return "block";
    });
    if (searchTerm) {
      node.style("opacity", function(d) {
        if (d3.select(this).style("display") === "none") return 0;
        var label = (d.label || d.id).toLowerCase();
        return label.indexOf(searchTerm) !== -1 ? 1 : 0.08;
      });
    } else if (!selectedNode) {
      node.style("opacity", function(d) {
        return d3.select(this).style("display") === "none" ? 0 : 1;
      });
    }
  }

  // -- Resize --
  window.addEventListener("resize", function() {
    var w = container.clientWidth;
    var h = container.clientHeight;
    svg.attr("width", w).attr("height", h);
    simulation.force("center", d3.forceCenter(w / 2, h / 2)).alpha(0.3).restart();
  });

  node.attr("data-node-id", function(d) { return d.id; });
}());
</script>
{% endblock %}
```

- [ ] **Step 2: Verify the template renders**

```bash
.venv/bin/python3 -m uvicorn app.main:app --port 8000 &
sleep 2
curl -s http://localhost:8000/graph | grep "topic-select" && echo "Topic switcher found" || echo "NOT found"
curl -s http://localhost:8000/graph?topic=all | grep "graph-stats" && echo "Stats found" || echo "NOT found"
kill %1
```

Expected: Both "found"

- [ ] **Step 3: Commit**

```bash
git add app/web/templates/graph.html
git commit -m "feat: rebuild graph template with full brain UI, topic switcher, dynamic legend"
```

---

### Task 7: Run the migration and verify end-to-end

**Files:**
- Run: `scripts/merge_agent_engine.py`

- [ ] **Step 1: Run the migration script**

```bash
.venv/bin/python3 scripts/merge_agent_engine.py
```

- [ ] **Step 2: Verify data counts**

```bash
.venv/bin/python3 -c "
from app.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
print('=== Post-merge counts ===')
for table in ['entity_nodes', 'knowledge_nodes', 'entity_edges', 'knowledge_edges', 'topic_profiles']:
    count = db.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()
    print(f'  {table}: {count}')
print()
print('=== Entity types ===')
rows = db.execute(text('SELECT entity_type, count(*) FROM entity_nodes GROUP BY entity_type ORDER BY count DESC')).fetchall()
for r in rows:
    print(f'  {r[0]}: {r[1]}')
print()
print('=== Knowledge kinds ===')
rows = db.execute(text('SELECT kind, count(*) FROM knowledge_nodes GROUP BY kind ORDER BY count DESC')).fetchall()
for r in rows:
    print(f'  {r[0]}: {r[1]}')
print()
print('=== Topics ===')
rows = db.execute(text('SELECT topic_key, display_name FROM topic_profiles ORDER BY topic_key')).fetchall()
for r in rows:
    print(f'  {r[0]}: {r[1]}')
print()
print('=== Marketing entities still intact ===')
rows = db.execute(text(\"SELECT canonical_name, entity_type FROM entity_nodes WHERE primary_topic_key = 'marketing' ORDER BY canonical_name\")).fetchall()
for r in rows:
    print(f'  {r[0]} ({r[1]})')
db.close()
"
```

Expected: Marketing entities (workflows, pillars, channels, partners, clients, competitors) still present with their original entity_types.

- [ ] **Step 3: Run the full test suite**

```bash
.venv/bin/python3 -m pytest tests/test_brain_query.py tests/test_memory_retrieval.py -v
```

Expected: ALL PASS

- [ ] **Step 4: Verify graph renders with topic switching**

```bash
.venv/bin/python3 -m uvicorn app.main:app --port 8000 &
sleep 2
# Marketing view (default)
curl -s "http://localhost:8000/graph" | grep -c "topic-select"
# All view
curl -s "http://localhost:8000/graph?topic=all" | grep -c '"group"'
# Work view
curl -s "http://localhost:8000/graph?topic=work" | grep -c '"group"'
kill %1
```

Expected: topic-select found in all responses, "all" view has more nodes than "marketing" view.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete brain merge — agent-engine data imported with topic switching"
```
