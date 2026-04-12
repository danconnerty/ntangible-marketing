"""Context assembly API for the MCP get_context tool."""
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.brain import EntityNode, KnowledgeNode, EntityEdge, KnowledgeEdge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["context"])


@router.get("/context")
def get_context_endpoint(
    q: str = Query(..., description="Search query"),
    topic: str | None = Query(None, description="Optional topic filter"),
    max_entities: int = Query(10, description="Max entities to return"),
    max_knowledge: int = Query(15, description="Max knowledge nodes to return"),
    db: Session = Depends(get_db),
):
    """Assemble a context packet from the knowledge graph."""
    search_terms = q.lower().split()

    # 1. Entity search
    entity_query = db.query(EntityNode)
    for term in search_terms:
        entity_query = entity_query.filter(EntityNode.canonical_name.ilike(f"%{term}%"))
    if topic:
        entity_query = entity_query.filter(EntityNode.primary_topic_key == topic)
    entities = entity_query.limit(max_entities).all()

    # 2. Edge expansion
    entity_results = []
    for ent in entities:
        edges_from = (
            db.query(EntityEdge)
            .filter(EntityEdge.source_id == ent.id)
            .limit(10)
            .all()
        )
        edges_to = (
            db.query(EntityEdge)
            .filter(EntityEdge.target_id == ent.id)
            .limit(10)
            .all()
        )

        edge_list = []
        for e in edges_from:
            target = db.query(EntityNode).filter(EntityNode.id == e.target_id).first()
            edge_list.append({
                "relation": e.relation,
                "target": target.canonical_name if target else str(e.target_id),
                "type": "entity",
            })
        for e in edges_to:
            source = db.query(EntityNode).filter(EntityNode.id == e.source_id).first()
            edge_list.append({
                "relation": e.relation,
                "target": source.canonical_name if source else str(e.source_id),
                "type": "entity",
            })

        entity_results.append({
            "name": ent.canonical_name,
            "type": ent.entity_type,
            "description": ent.description or "",
            "topic": ent.primary_topic_key,
            "edges": edge_list,
        })

    # 3. Knowledge search
    knowledge_query = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.is_latest == True)  # noqa: E712
    )
    for term in search_terms:
        knowledge_query = knowledge_query.filter(
            KnowledgeNode.title.ilike(f"%{term}%")
            | KnowledgeNode.content.ilike(f"%{term}%")
        )
    if topic:
        knowledge_query = knowledge_query.filter(KnowledgeNode.primary_topic_key == topic)
    knowledge_nodes = knowledge_query.limit(max_knowledge).all()

    # 4. Knowledge edges
    knowledge_results = []
    for kn in knowledge_nodes:
        k_edges = (
            db.query(KnowledgeEdge)
            .filter((KnowledgeEdge.source_id == kn.id) | (KnowledgeEdge.target_id == kn.id))
            .limit(5)
            .all()
        )
        edge_list = []
        for ke in k_edges:
            other_id = ke.target_id if ke.source_id == kn.id else ke.source_id
            other = db.query(KnowledgeNode).filter(KnowledgeNode.id == other_id).first()
            edge_list.append({
                "relation": ke.relation,
                "target": other.title if other else str(other_id),
                "type": "knowledge",
            })

        knowledge_results.append({
            "kind": kn.kind,
            "title": kn.title,
            "content": (kn.content or "")[:500],
            "confidence": kn.confidence,
            "topic": kn.primary_topic_key,
            "edges": edge_list,
        })

    return {
        "entities": entity_results,
        "knowledge": knowledge_results,
        "query": q,
        "entity_count": len(entity_results),
        "knowledge_count": len(knowledge_results),
    }
