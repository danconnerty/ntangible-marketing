"""BrainQuery — primary interface for reading and writing brain table data.

Services should use BrainQuery instead of querying brain models directly.
All write methods call db.flush() rather than db.commit() so callers control
the transaction boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.brain import EntityEdge, EntityNode, KnowledgeEdge, KnowledgeNode


class BrainQuery:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Knowledge node queries
    # ------------------------------------------------------------------

    def list_drafts_by_status(
        self,
        status: str,
        *,
        limit: int = 50,
        platform: str | None = None,
    ) -> list[KnowledgeNode]:
        """Return draft KnowledgeNodes with the given status.

        When *platform* is provided the filter is applied via a JSONB text
        extraction in Postgres (``metadata->>'platform'``).  In SQLite test
        environments the JSONB operator is not available, so the platform
        filter is silently skipped — callers should not rely on it in
        non-Postgres environments.
        """
        q = self.db.query(KnowledgeNode).filter(
            KnowledgeNode.kind == "draft",
            KnowledgeNode.status == status,
        )
        if platform is not None:
            try:
                q = q.filter(
                    KnowledgeNode.metadata_.op("->>")(  # type: ignore[attr-defined]
                        "platform"
                    )
                    == platform
                )
            except Exception:
                # Fallback for non-Postgres environments (e.g. SQLite tests)
                pass
        return q.limit(limit).all()

    def list_publishable_drafts(
        self,
        now: datetime,
        *,
        limit: int = 50,
    ) -> list[KnowledgeNode]:
        """Drafts ready to publish: status='scheduled', valid_from <= now."""
        return (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.kind == "draft",
                KnowledgeNode.status == "scheduled",
                KnowledgeNode.valid_from <= now,
            )
            .order_by(KnowledgeNode.valid_from.asc())
            .limit(limit)
            .all()
        )

    def list_expirable_drafts(
        self,
        now: datetime,
        *,
        limit: int = 50,
    ) -> list[KnowledgeNode]:
        """Drafts to expire: status='review_required', valid_until <= now."""
        return (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.kind == "draft",
                KnowledgeNode.status == "review_required",
                KnowledgeNode.valid_until <= now,
            )
            .order_by(KnowledgeNode.valid_until.asc())
            .limit(limit)
            .all()
        )

    def list_due_schedule_rules(
        self,
        now: datetime,  # noqa: ARG002 — available to callers; next_fire_at is in JSONB
        *,
        limit: int = 50,
    ) -> list[KnowledgeNode]:
        """Active schedule_rule nodes ordered by creation time.

        Filtering by ``next_fire_at`` is intentionally left to the caller
        because that field lives inside the JSONB metadata blob.
        """
        return (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.kind == "schedule_rule",
                KnowledgeNode.status == "active",
            )
            .order_by(KnowledgeNode.created_at.asc())
            .limit(limit)
            .all()
        )

    def list_knowledge_by_kind(
        self,
        kind: str,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeNode]:
        """Return KnowledgeNodes of the given *kind*, optionally filtered by status."""
        q = self.db.query(KnowledgeNode).filter(KnowledgeNode.kind == kind)
        if status is not None:
            q = q.filter(KnowledgeNode.status == status)
        return q.limit(limit).all()

    def get_knowledge_node(self, node_id: uuid.UUID) -> KnowledgeNode | None:
        """Return a single KnowledgeNode by primary key, or None."""
        return (
            self.db.query(KnowledgeNode)
            .filter(KnowledgeNode.id == node_id)
            .first()
        )

    def create_draft(
        self,
        *,
        title: str,
        content: str,
        platform: str,
        intent: str = "brand",
        pillar: str = "thought_leadership",
        hashtags: list[str] | None = None,
        mode: str = "manual",
        status: str = "pending",
        confidence: float = 0.5,
        trust_score: float = 0.5,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> KnowledgeNode:
        """Create and flush a new draft KnowledgeNode."""
        meta: dict[str, Any] = {
            "platform": platform,
            "intent": intent,
            "pillar": pillar,
            "hashtags": hashtags or [],
            "mode": mode,
        }
        if extra_metadata:
            meta.update(extra_metadata)

        node = KnowledgeNode(
            id=uuid.uuid4(),
            kind="draft",
            title=title,
            content=content,
            primary_topic_key="marketing",
            confidence=confidence,
            trust_score=trust_score,
            status=status,
            valid_from=valid_from,
            valid_until=valid_until,
            metadata_=meta,
        )
        self.db.add(node)
        self.db.flush()
        return node

    def create_knowledge_node(
        self,
        *,
        kind: str,
        title: str,
        content: str | None = None,
        status: str = "active",
        confidence: float = 0.5,
        trust_score: float = 0.5,
        primary_topic_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeNode:
        """Create and flush a generic KnowledgeNode."""
        node = KnowledgeNode(
            id=uuid.uuid4(),
            kind=kind,
            title=title,
            content=content,
            status=status,
            confidence=confidence,
            trust_score=trust_score,
            primary_topic_key=primary_topic_key,
            metadata_=metadata or {},
        )
        self.db.add(node)
        self.db.flush()
        return node

    # ------------------------------------------------------------------
    # Entity node queries
    # ------------------------------------------------------------------

    def list_entities_by_type(
        self,
        entity_type: str,
        *,
        status: str = "active",
        limit: int = 50,
    ) -> list[EntityNode]:
        """Return EntityNodes of the given type and status."""
        return (
            self.db.query(EntityNode)
            .filter(
                EntityNode.entity_type == entity_type,
                EntityNode.status == status,
            )
            .limit(limit)
            .all()
        )

    def get_entity(self, entity_id: uuid.UUID) -> EntityNode | None:
        """Return a single EntityNode by primary key, or None."""
        return (
            self.db.query(EntityNode)
            .filter(EntityNode.id == entity_id)
            .first()
        )

    def get_entity_by_slug(
        self,
        entity_type: str,
        slug: str,
    ) -> EntityNode | None:
        """Return an EntityNode by (entity_type, slug), or None."""
        return (
            self.db.query(EntityNode)
            .filter(
                EntityNode.entity_type == entity_type,
                EntityNode.slug == slug,
            )
            .first()
        )

    def create_entity(
        self,
        *,
        entity_type: str,
        canonical_name: str,
        slug: str,
        status: str = "active",
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        primary_topic_key: str | None = None,
    ) -> EntityNode:
        """Create and flush a new EntityNode."""
        entity = EntityNode(
            id=uuid.uuid4(),
            entity_type=entity_type,
            canonical_name=canonical_name,
            slug=slug,
            status=status,
            description=description,
            primary_topic_key=primary_topic_key,
            metadata_=metadata or {},
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    # ------------------------------------------------------------------
    # Edge queries
    # ------------------------------------------------------------------

    def get_edges_from(
        self,
        source_id: uuid.UUID,
        *,
        relation: str | None = None,
    ) -> list[EntityEdge]:
        """Return edges originating from *source_id*."""
        q = self.db.query(EntityEdge).filter(EntityEdge.source_id == source_id)
        if relation is not None:
            q = q.filter(EntityEdge.relation == relation)
        return q.all()

    def get_edges_to(
        self,
        target_id: uuid.UUID,
        *,
        relation: str | None = None,
    ) -> list[EntityEdge]:
        """Return edges pointing to *target_id*."""
        q = self.db.query(EntityEdge).filter(EntityEdge.target_id == target_id)
        if relation is not None:
            q = q.filter(EntityEdge.relation == relation)
        return q.all()

    def create_edge(
        self,
        *,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        source_type: str,
        target_type: str,
        relation: str,
        confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EntityEdge:
        """Create and flush a new EntityEdge."""
        edge = EntityEdge(
            id=uuid.uuid4(),
            source_id=source_id,
            target_id=target_id,
            source_type=source_type,
            target_type=target_type,
            relation=relation,
            confidence=confidence,
            metadata_=metadata or {},
        )
        self.db.add(edge)
        self.db.flush()
        return edge

    def get_workflow_for_draft(
        self,
        draft_id: uuid.UUID,
    ) -> EntityNode | None:
        """Return the workflow EntityNode that produced *draft_id*.

        Looks for an EntityEdge where target_id=draft_id, source_type='entity',
        target_type='knowledge', relation='produced', then returns the source
        EntityNode.
        """
        edge = (
            self.db.query(EntityEdge)
            .filter(
                EntityEdge.target_id == draft_id,
                EntityEdge.source_type == "entity",
                EntityEdge.target_type == "knowledge",
                EntityEdge.relation == "produced",
            )
            .first()
        )
        if edge is None:
            return None
        return self.get_entity(edge.source_id)

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

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
                EntityEdge.source_id.in_(all_node_ids),
                EntityEdge.target_id.in_(all_node_ids),
            )
            .all()
            if all_node_ids
            else []
        )

        knowledge_edges = (
            self.db.query(KnowledgeEdge)
            .filter(
                KnowledgeEdge.source_id.in_(knowledge_ids),
                KnowledgeEdge.target_id.in_(knowledge_ids),
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
