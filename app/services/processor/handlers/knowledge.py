"""Knowledge extraction handler. Two-stage: extract entities, then run intelligence reasoning."""
from __future__ import annotations
import logging
import re
from sqlalchemy.orm import Session
from app.services.brain_query import BrainQuery
from app.services.processor.classifier import ClassificationResult
from app.services.processor.intelligence import run_intelligence_stage, IntelligenceResult
from app.services.processor.handlers.base import HandlerResult

logger = logging.getLogger(__name__)

MARKETING_ENTITY_TYPES = {"partner", "client", "competitor", "workflow", "content_pillar", "publishing_channel"}
ENTITY_TYPE_TOPIC_DEFAULTS = {
    "person": "people",
    "company": "work",
    "org": "work",
    "place": "work",
    "product": "projects",
    "topic": None,
}


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _assign_topic_key(entity_type: str, classifier_topic: str | None) -> str | None:
    if entity_type in MARKETING_ENTITY_TYPES:
        return "marketing"
    default = ENTITY_TYPE_TOPIC_DEFAULTS.get(entity_type)
    if default is not None:
        return default
    return classifier_topic


def resolve_entity(bq: BrainQuery, *, name: str, entity_type: str, topic_key: str | None = None) -> tuple:
    slug = _slugify(name)
    existing = bq.get_entity_by_slug(entity_type, slug)
    if existing is not None:
        return existing, False
    assigned_topic = _assign_topic_key(entity_type, topic_key)
    entity = bq.create_entity(
        entity_type=entity_type, canonical_name=name, slug=slug,
        primary_topic_key=assigned_topic,
    )
    logger.info("Created new entity: %s/%s (%s) topic=%s", entity_type, slug, name, assigned_topic)
    return entity, True


def _build_graph_context(bq: BrainQuery, resolved_entities: list[dict]) -> dict:
    from app.models.brain import KnowledgeNode
    entities_context = []
    for ent in resolved_entities:
        entity_id = ent["entity_id"]
        edges_from = bq.get_edges_from(entity_id)
        edges_to = bq.get_edges_to(entity_id)
        edges = [
            {"relation": e.relation, "target": str(e.target_id)} for e in edges_from
        ] + [
            {"relation": e.relation, "target": str(e.source_id)} for e in edges_to
        ]
        knowledge = []
        knowledge_nodes = (
            bq.db.query(KnowledgeNode)
            .filter(KnowledgeNode.is_latest == True)  # noqa: E712
            .filter(KnowledgeNode.content.ilike(f"%{ent['name']}%"))
            .limit(10)
            .all()
        )
        for kn in knowledge_nodes:
            knowledge.append({"id": str(kn.id), "title": kn.title, "kind": kn.kind, "confidence": kn.confidence})

        entities_context.append({
            "name": ent["name"],
            "type": ent["type"],
            "edges": edges[:10],
            "knowledge": knowledge[:10],
        })
    return {"entities": entities_context}


def handle(*, db: Session, raw_payload: dict, classification: ClassificationResult) -> HandlerResult | None:
    if not classification.is_knowledge:
        return None

    bq = BrainQuery(db)
    entities_created = 0
    entities_resolved = 0
    resolved_entities = []

    for ent_data in classification.knowledge_entities:
        name = ent_data.get("name", "").strip()
        entity_type = ent_data.get("type", "topic").strip().lower()
        if not name:
            continue
        entity, was_created = resolve_entity(
            bq, name=name, entity_type=entity_type, topic_key=classification.topic_key,
        )
        if was_created:
            entities_created += 1
        else:
            entities_resolved += 1
        resolved_entities.append({
            "entity_id": str(entity.id),
            "name": name,
            "type": entity_type,
            "relation": ent_data.get("relation", ""),
            "created": was_created,
        })

    knowledge_node = bq.create_knowledge_node(
        kind=classification.knowledge_kind or "fact",
        title=classification.summary,
        content=f"Source: {raw_payload.get('from', raw_payload.get('file_name', 'unknown'))}",
        confidence=classification.confidence,
        trust_score=classification.confidence,
        primary_topic_key=classification.topic_key,
        metadata={
            "entities": resolved_entities,
            "source_type": raw_payload.get("source_type", "unknown"),
            "ingestion_source": "processor",
        },
    )

    basic_edges = 0
    for i, ent_a in enumerate(resolved_entities):
        for ent_b in resolved_entities[i + 1:]:
            bq.create_edge(
                source_id=ent_a["entity_id"],
                target_id=ent_b["entity_id"],
                source_type="entity",
                target_type="entity",
                relation=ent_a.get("relation") or "related_to",
            )
            basic_edges += 1

    graph_context = _build_graph_context(bq, resolved_entities)
    stage1_output = {
        "summary": classification.summary,
        "knowledge_kind": classification.knowledge_kind,
        "entities": classification.knowledge_entities,
    }

    intelligence_edges = 0
    implications_stored = False
    try:
        intel_result = run_intelligence_stage(stage1_output=stage1_output, graph_context=graph_context)

        for edge in intel_result.new_edges:
            source_name = edge.get("source", "")
            target_name = edge.get("target", "")
            source_ent = next((e for e in resolved_entities if e["name"] == source_name), None)
            target_ent = next((e for e in resolved_entities if e["name"] == target_name), None)
            if source_ent and target_ent:
                bq.create_edge(
                    source_id=source_ent["entity_id"],
                    target_id=target_ent["entity_id"],
                    source_type="entity",
                    target_type="entity",
                    relation=edge.get("relation", "related_to"),
                    confidence=edge.get("confidence"),
                )
                intelligence_edges += 1

        for update in intel_result.updated_knowledge:
            old_id = update.get("id")
            if old_id:
                old_node = bq.get_knowledge_node(old_id)
                if old_node and old_node.is_latest:
                    old_node.is_latest = False
                    old_node.superseded_by = knowledge_node.id
                    db.flush()
                    logger.info("Superseded knowledge node %s", old_id)

        if intel_result.implications:
            bq.create_knowledge_node(
                kind="observation",
                title=f"Implication: {classification.summary}",
                content=intel_result.implications,
                confidence=classification.confidence * 0.8,
                trust_score=classification.confidence * 0.8,
                primary_topic_key=classification.topic_key,
                metadata={"source_knowledge_id": str(knowledge_node.id), "ingestion_source": "processor_intelligence"},
            )
            implications_stored = True
    except Exception:
        logger.exception("Intelligence stage failed for item, continuing with basic extraction")

    logger.info(
        "Knowledge handler: %d entities (%d new, %d resolved), %d basic edges, %d intel edges, implications=%s, knowledge_node=%s",
        len(resolved_entities), entities_created, entities_resolved, basic_edges, intelligence_edges, implications_stored, knowledge_node.id,
    )

    return HandlerResult(
        handler_name="knowledge",
        success=True,
        detail={
            "entities_created": entities_created,
            "entities_resolved": entities_resolved,
            "basic_edges": basic_edges,
            "intelligence_edges": intelligence_edges,
            "implications": implications_stored,
            "entities": resolved_entities,
            "knowledge_node_id": str(knowledge_node.id),
            "knowledge_kind": classification.knowledge_kind,
            "topic_key": classification.topic_key,
        },
    )
