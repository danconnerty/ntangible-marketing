# Marketing Brain Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace NTangible's ~40 marketing tables with 5 brain tables (topic_profiles, entity_nodes, knowledge_nodes, entity_edges, knowledge_edges) while keeping the UI, agent workflows, and publishing pipeline functionally identical.

**Architecture:** Schema swap — create brain SQLAlchemy models, write an Alembic migration that creates new tables and migrates all existing data, then update all services and routes to query brain tables. Publishers and templates remain unchanged.

**Tech Stack:** Python 3.13, SQLAlchemy, Alembic, FastAPI, PostgreSQL, pytest

**Spec:** `docs/superpowers/specs/2026-04-09-marketing-brain-integration-design.md` (in agent-engine repo)

---

## File Structure

### New Files
- `app/models/brain.py` — 5 SQLAlchemy models: TopicProfile, EntityNode, KnowledgeNode, EntityEdge, KnowledgeEdge
- `app/services/brain_query.py` — Query helpers that translate brain nodes into shapes the existing services/routes expect
- `alembic/versions/20260409_brain_schema_migration.py` — Create brain tables, migrate data, drop old tables
- `app/web/templates/graph.html` — Graph view template
- `tests/test_brain_models.py` — Brain model tests
- `tests/test_brain_query.py` — Brain query helper tests

### Modified Files
- `app/models/__init__.py` — Export brain models, remove old model exports
- `app/database.py` — No changes needed
- `app/services/review_queue.py` — Use brain queries
- `app/services/scheduler.py` — Use brain queries
- `app/services/trigger_engine.py` — Use brain models
- `app/services/workflow_engine.py` — Use brain models
- `app/services/x_pipeline.py` — Use brain models
- `app/services/linkedin_pipeline.py` — Use brain models
- `app/services/instagram_pipeline.py` — Use brain models
- `app/services/blog_service.py` — Use brain models
- `app/services/publishing_connection_service.py` — Use brain models
- `app/services/analytics_ingest.py` — Use brain models
- `app/services/campaign_service.py` — Use brain models
- `app/services/competitor_service.py` — Use brain models
- `app/services/lead_nurture_service.py` — Use brain models
- `app/services/partner_intake_service.py` — Use brain models
- `app/services/partner_delivery_service.py` — Use brain models
- `app/services/revenue_service.py` — Use brain models
- `app/services/sports_calendar_service.py` — Use brain models
- `app/services/repurposing_service.py` — Use brain models
- `app/services/ugc_service.py` — Use brain models
- `app/services/video_service.py` — Use brain models
- `app/services/science_content_service.py` — Use brain models
- `app/services/prompt_assembler.py` — Use brain models
- `app/services/memory_retrieval.py` — Use brain models
- `app/services/workflow_editor.py` — Use brain models
- `app/services/automatic_control.py` — Use brain models
- `app/services/platform_generation.py` — Use brain models
- `app/web/routes.py` — Update all data loaders and action handlers
- `alembic/env.py` — Import brain models instead of old models
- All test files — Update for brain models

### Unchanged Files
- `app/publishers/*` — All publishers stay as-is
- `app/web/templates/*` (except new graph.html) — All templates stay as-is
- `app/auth.py` — Authentication unchanged
- `app/agents/*` — Content generation and compliance unchanged
- `app/schemas/*` — Workflow config schemas unchanged

---

## Task 1: Create Brain SQLAlchemy Models

**Files:**
- Create: `app/models/brain.py`
- Test: `tests/test_brain_models.py`

- [ ] **Step 1: Write failing test for brain models**

```python
# tests/test_brain_models.py
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_create_topic_profile(db: Session):
    from app.models.brain import TopicProfile

    topic = TopicProfile(
        topic_key="marketing",
        display_name="Marketing",
        description="Strategy, content, campaigns, posts, and publishing.",
        priority="critical",
    )
    db.add(topic)
    db.flush()
    assert topic.id is not None
    assert topic.topic_key == "marketing"
    assert topic.enabled is True


def test_create_entity_node(db: Session):
    from app.models.brain import EntityNode

    entity = EntityNode(
        entity_type="workflow",
        canonical_name="LinkedIn Daily Post",
        slug="linkedin-daily-post",
        status="active",
        primary_topic_key="marketing",
        metadata_={"mode": "automatic", "platform": "linkedin", "enabled": True},
    )
    db.add(entity)
    db.flush()
    assert entity.id is not None
    assert entity.entity_type == "workflow"
    assert entity.metadata_["platform"] == "linkedin"


def test_create_knowledge_node(db: Session):
    from app.models.brain import KnowledgeNode

    node = KnowledgeNode(
        kind="draft",
        title="Why blind spots cost athletes",
        content="Your athlete might be losing ground without knowing it...",
        primary_topic_key="marketing",
        confidence=0.85,
        trust_score=0.9,
        status="review_required",
        metadata_={
            "platform": "linkedin",
            "intent": "brand",
            "pillar": "blind_spot",
            "hashtags": ["#sportstech"],
            "mode": "manual",
        },
    )
    db.add(node)
    db.flush()
    assert node.id is not None
    assert node.kind == "draft"
    assert node.status == "review_required"
    assert node.is_latest is True


def test_create_entity_edge(db: Session):
    from app.models.brain import EntityEdge, EntityNode, KnowledgeNode

    workflow = EntityNode(
        entity_type="workflow",
        canonical_name="LinkedIn Workflow",
        slug="linkedin-wf",
        status="active",
        primary_topic_key="marketing",
    )
    draft = KnowledgeNode(
        kind="draft",
        title="Test draft",
        content="Content here",
        primary_topic_key="marketing",
        confidence=0.8,
        trust_score=0.8,
        status="pending",
    )
    db.add_all([workflow, draft])
    db.flush()

    edge = EntityEdge(
        source_id=workflow.id,
        target_id=draft.id,
        source_type="entity",
        target_type="knowledge",
        relation="produced",
    )
    db.add(edge)
    db.flush()
    assert edge.id is not None
    assert edge.relation == "produced"


def test_create_knowledge_edge(db: Session):
    from app.models.brain import KnowledgeEdge, KnowledgeNode

    draft = KnowledgeNode(
        kind="draft",
        title="Original",
        content="V1",
        primary_topic_key="marketing",
        confidence=0.8,
        trust_score=0.8,
        status="superseded",
    )
    revision = KnowledgeNode(
        kind="draft",
        title="Revision",
        content="V2",
        primary_topic_key="marketing",
        confidence=0.9,
        trust_score=0.9,
        status="review_required",
    )
    db.add_all([draft, revision])
    db.flush()

    edge = KnowledgeEdge(
        source_id=revision.id,
        target_id=draft.id,
        relation="supersedes",
    )
    db.add(edge)
    db.flush()
    assert edge.relation == "supersedes"


def test_entity_node_slug_unique_per_type(db: Session):
    from app.models.brain import EntityNode

    e1 = EntityNode(
        entity_type="workflow",
        canonical_name="WF1",
        slug="same-slug",
        status="active",
        primary_topic_key="marketing",
    )
    e2 = EntityNode(
        entity_type="campaign",
        canonical_name="Camp1",
        slug="same-slug",
        status="active",
        primary_topic_key="marketing",
    )
    db.add_all([e1, e2])
    db.flush()
    # Different entity_types can share a slug
    assert e1.slug == e2.slug
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_brain_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.brain'`

- [ ] **Step 3: Write brain models**

```python
# app/models/brain.py
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TopicProfile(Base):
    __tablename__ = "topic_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[str] = mapped_column(
        String(32), nullable=False, default="high"
    )
    keywords: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    context_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    intelligence_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EntityNode(Base):
    __tablename__ = "entity_nodes"

    __table_args__ = (
        UniqueConstraint("entity_type", "slug", name="uq_entity_type_slug"),
        Index("ix_entity_type_status", "entity_type", "status"),
        Index("ix_entity_topic", "primary_topic_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(256), nullable=False)
    slug: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active"
    )
    primary_topic_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    search_tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"

    __table_args__ = (
        Index("ix_knowledge_kind_status", "kind", "status"),
        Index("ix_knowledge_topic", "primary_topic_key"),
        Index("ix_knowledge_scheduler", "status", "valid_from"),
        Index("ix_knowledge_latest", "kind", "status", "is_latest"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_topic_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    search_tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EntityEdge(Base):
    __tablename__ = "entity_edges"

    __table_args__ = (
        Index("ix_entity_edge_source", "source_id"),
        Index("ix_entity_edge_target", "target_id"),
        Index("ix_entity_edge_source_rel", "source_id", "relation"),
        Index("ix_entity_edge_target_rel", "target_id", "relation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    relation: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"

    __table_args__ = (
        Index("ix_knowledge_edge_source", "source_id"),
        Index("ix_knowledge_edge_target", "target_id"),
        Index("ix_knowledge_edge_source_rel", "source_id", "relation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    relation: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_brain_models.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/brain.py tests/test_brain_models.py
git commit -m "feat: add brain SQLAlchemy models (topic_profiles, entity_nodes, knowledge_nodes, edges)"
```

---

## Task 2: Create Brain Query Helpers

The query helpers bridge the brain schema and the shapes the existing services/routes expect. This is the critical abstraction — services call these helpers instead of querying old models directly.

**Files:**
- Create: `app/services/brain_query.py`
- Test: `tests/test_brain_query.py`

- [ ] **Step 1: Write failing tests for brain query helpers**

```python
# tests/test_brain_query.py
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.brain import EntityNode, KnowledgeNode, EntityEdge


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def seeded_db(db: Session):
    """Seed with a workflow entity, a draft, and an edge linking them."""
    workflow = EntityNode(
        entity_type="workflow",
        canonical_name="LinkedIn Daily",
        slug="linkedin-daily",
        status="active",
        primary_topic_key="marketing",
        metadata_={"mode": "manual", "platform": "linkedin", "enabled": True},
    )
    draft = KnowledgeNode(
        kind="draft",
        title="Test draft",
        content="Post content here",
        primary_topic_key="marketing",
        confidence=0.85,
        trust_score=0.9,
        status="review_required",
        metadata_={
            "platform": "linkedin",
            "intent": "brand",
            "pillar": "thought_leadership",
            "hashtags": ["#test"],
            "mode": "manual",
        },
    )
    db.add_all([workflow, draft])
    db.flush()
    edge = EntityEdge(
        source_id=workflow.id,
        target_id=draft.id,
        source_type="entity",
        target_type="knowledge",
        relation="produced",
    )
    db.add(edge)
    db.flush()
    return db, workflow, draft


def test_list_drafts_by_status(seeded_db):
    from app.services.brain_query import BrainQuery

    db, workflow, draft = seeded_db
    bq = BrainQuery(db)
    results = bq.list_drafts_by_status("review_required")
    assert len(results) == 1
    assert results[0].id == draft.id


def test_list_drafts_by_status_empty(db: Session):
    from app.services.brain_query import BrainQuery

    bq = BrainQuery(db)
    results = bq.list_drafts_by_status("review_required")
    assert results == []


def test_get_entity_by_slug(seeded_db):
    from app.services.brain_query import BrainQuery

    db, workflow, _ = seeded_db
    bq = BrainQuery(db)
    result = bq.get_entity_by_slug("workflow", "linkedin-daily")
    assert result is not None
    assert result.id == workflow.id


def test_get_workflow_for_draft(seeded_db):
    from app.services.brain_query import BrainQuery

    db, workflow, draft = seeded_db
    bq = BrainQuery(db)
    result = bq.get_workflow_for_draft(draft.id)
    assert result is not None
    assert result.id == workflow.id


def test_list_due_schedule_rules(db: Session):
    from app.services.brain_query import BrainQuery

    now = datetime.now(timezone.utc)
    rule = KnowledgeNode(
        kind="schedule_rule",
        title="Daily 9am",
        primary_topic_key="marketing",
        confidence=1.0,
        trust_score=1.0,
        status="active",
        metadata_={
            "cron_expression": "0 9 * * *",
            "timezone": "America/New_York",
            "next_fire_at": (now - timedelta(minutes=5)).isoformat(),
            "workflow_entity_id": str(uuid.uuid4()),
        },
    )
    db.add(rule)
    db.flush()

    bq = BrainQuery(db)
    results = bq.list_due_schedule_rules(now)
    assert len(results) == 1


def test_list_publishable_drafts(db: Session):
    from app.services.brain_query import BrainQuery

    now = datetime.now(timezone.utc)
    draft = KnowledgeNode(
        kind="draft",
        title="Scheduled draft",
        content="Content",
        primary_topic_key="marketing",
        confidence=0.9,
        trust_score=0.9,
        status="scheduled",
        valid_from=now - timedelta(minutes=1),
        metadata_={"platform": "linkedin", "mode": "manual"},
    )
    db.add(draft)
    db.flush()

    bq = BrainQuery(db)
    results = bq.list_publishable_drafts(now)
    assert len(results) == 1


def test_list_expirable_drafts(db: Session):
    from app.services.brain_query import BrainQuery

    now = datetime.now(timezone.utc)
    draft = KnowledgeNode(
        kind="draft",
        title="Expiring draft",
        content="Content",
        primary_topic_key="marketing",
        confidence=0.9,
        trust_score=0.9,
        status="review_required",
        valid_until=now - timedelta(minutes=1),
        metadata_={"platform": "x", "mode": "manual"},
    )
    db.add(draft)
    db.flush()

    bq = BrainQuery(db)
    results = bq.list_expirable_drafts(now)
    assert len(results) == 1


def test_create_draft_node(db: Session):
    from app.services.brain_query import BrainQuery

    bq = BrainQuery(db)
    draft = bq.create_draft(
        title="New post",
        content="Post text",
        platform="linkedin",
        intent="brand",
        pillar="thought_leadership",
        hashtags=["#test"],
        mode="manual",
        status="review_required",
    )
    assert draft.id is not None
    assert draft.kind == "draft"
    assert draft.metadata_["platform"] == "linkedin"


def test_create_edge(seeded_db):
    from app.services.brain_query import BrainQuery

    db, workflow, draft = seeded_db
    bq = BrainQuery(db)
    edge = bq.create_edge(
        source_id=workflow.id,
        target_id=draft.id,
        source_type="entity",
        target_type="knowledge",
        relation="produced",
    )
    assert edge.id is not None


def test_list_entities_by_type(seeded_db):
    from app.services.brain_query import BrainQuery

    db, workflow, _ = seeded_db
    bq = BrainQuery(db)
    results = bq.list_entities_by_type("workflow")
    assert len(results) == 1
    assert results[0].id == workflow.id


def test_get_edges_for_node(seeded_db):
    from app.services.brain_query import BrainQuery

    db, workflow, draft = seeded_db
    bq = BrainQuery(db)
    edges = bq.get_edges_from(workflow.id)
    assert len(edges) == 1
    assert edges[0].target_id == draft.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_brain_query.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.brain_query'`

- [ ] **Step 3: Write brain query helpers**

```python
# app/services/brain_query.py
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.brain import EntityEdge, EntityNode, KnowledgeEdge, KnowledgeNode


class BrainQuery:
    def __init__(self, db: Session):
        self.db = db

    # --- Knowledge Node queries ---

    def list_drafts_by_status(
        self, status: str, *, limit: int = 50, platform: str | None = None
    ) -> list[KnowledgeNode]:
        q = (
            self.db.query(KnowledgeNode)
            .filter(KnowledgeNode.kind == "draft", KnowledgeNode.status == status)
        )
        if platform:
            q = q.filter(
                KnowledgeNode.metadata_.op("->>")("platform") == platform
            )
        return q.order_by(KnowledgeNode.created_at.desc()).limit(limit).all()

    def list_publishable_drafts(
        self, now: datetime, *, limit: int = 50
    ) -> list[KnowledgeNode]:
        return (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.kind == "draft",
                KnowledgeNode.status == "scheduled",
                KnowledgeNode.valid_from.isnot(None),
                KnowledgeNode.valid_from <= now,
            )
            .order_by(KnowledgeNode.valid_from.asc())
            .limit(limit)
            .all()
        )

    def list_expirable_drafts(
        self, now: datetime, *, limit: int = 50
    ) -> list[KnowledgeNode]:
        return (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.kind == "draft",
                KnowledgeNode.status == "review_required",
                KnowledgeNode.valid_until.isnot(None),
                KnowledgeNode.valid_until <= now,
            )
            .order_by(KnowledgeNode.valid_until.asc())
            .limit(limit)
            .all()
        )

    def list_due_schedule_rules(
        self, now: datetime, *, limit: int = 50
    ) -> list[KnowledgeNode]:
        return (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.kind == "schedule_rule",
                KnowledgeNode.status == "active",
                KnowledgeNode.metadata_.op("->>")("next_fire_at").isnot(None),
            )
            .order_by(KnowledgeNode.created_at.asc())
            .limit(limit)
            .all()
        )

    def list_knowledge_by_kind(
        self, kind: str, *, status: str | None = None, limit: int = 50
    ) -> list[KnowledgeNode]:
        q = self.db.query(KnowledgeNode).filter(KnowledgeNode.kind == kind)
        if status:
            q = q.filter(KnowledgeNode.status == status)
        return q.order_by(KnowledgeNode.created_at.desc()).limit(limit).all()

    def get_knowledge_node(self, node_id: uuid.UUID) -> KnowledgeNode | None:
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
        extra_metadata: dict | None = None,
    ) -> KnowledgeNode:
        metadata = {
            "platform": platform,
            "intent": intent,
            "pillar": pillar,
            "hashtags": hashtags or [],
            "mode": mode,
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        node = KnowledgeNode(
            kind="draft",
            title=title,
            content=content,
            primary_topic_key="marketing",
            confidence=confidence,
            trust_score=trust_score,
            status=status,
            valid_from=valid_from,
            valid_until=valid_until,
            metadata_=metadata,
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
        metadata: dict | None = None,
    ) -> KnowledgeNode:
        node = KnowledgeNode(
            kind=kind,
            title=title,
            content=content,
            primary_topic_key="marketing",
            confidence=confidence,
            trust_score=trust_score,
            status=status,
            metadata_=metadata or {},
        )
        self.db.add(node)
        self.db.flush()
        return node

    # --- Entity Node queries ---

    def list_entities_by_type(
        self, entity_type: str, *, status: str = "active", limit: int = 50
    ) -> list[EntityNode]:
        return (
            self.db.query(EntityNode)
            .filter(
                EntityNode.entity_type == entity_type,
                EntityNode.status == status,
            )
            .order_by(EntityNode.canonical_name.asc())
            .limit(limit)
            .all()
        )

    def get_entity(self, entity_id: uuid.UUID) -> EntityNode | None:
        return (
            self.db.query(EntityNode)
            .filter(EntityNode.id == entity_id)
            .first()
        )

    def get_entity_by_slug(
        self, entity_type: str, slug: str
    ) -> EntityNode | None:
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
        metadata: dict | None = None,
    ) -> EntityNode:
        entity = EntityNode(
            entity_type=entity_type,
            canonical_name=canonical_name,
            slug=slug,
            status=status,
            description=description,
            primary_topic_key="marketing",
            metadata_=metadata or {},
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    # --- Edge queries ---

    def get_edges_from(
        self, source_id: uuid.UUID, *, relation: str | None = None
    ) -> list[EntityEdge]:
        q = self.db.query(EntityEdge).filter(EntityEdge.source_id == source_id)
        if relation:
            q = q.filter(EntityEdge.relation == relation)
        return q.all()

    def get_edges_to(
        self, target_id: uuid.UUID, *, relation: str | None = None
    ) -> list[EntityEdge]:
        q = self.db.query(EntityEdge).filter(EntityEdge.target_id == target_id)
        if relation:
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
        metadata: dict | None = None,
    ) -> EntityEdge:
        edge = EntityEdge(
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
        self, draft_id: uuid.UUID
    ) -> EntityNode | None:
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
        if not edge:
            return None
        return self.get_entity(edge.source_id)

    # --- Graph queries ---

    def get_graph_data(
        self, *, topic_key: str = "marketing"
    ) -> dict:
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
        all_ids = entity_ids | knowledge_ids

        entity_edges = (
            self.db.query(EntityEdge)
            .filter(
                EntityEdge.source_id.in_(all_ids),
                EntityEdge.target_id.in_(all_ids),
            )
            .all()
        )
        knowledge_edges = (
            self.db.query(KnowledgeEdge)
            .filter(
                KnowledgeEdge.source_id.in_(knowledge_ids),
                KnowledgeEdge.target_id.in_(knowledge_ids),
            )
            .all()
        )
        return {
            "entities": entities,
            "knowledge": knowledge,
            "entity_edges": entity_edges,
            "knowledge_edges": knowledge_edges,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_brain_query.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/brain_query.py tests/test_brain_query.py
git commit -m "feat: add brain query helpers for service layer"
```

---

## Task 3: Update models/__init__.py and alembic/env.py

**Files:**
- Modify: `app/models/__init__.py`
- Modify: `alembic/env.py`

- [ ] **Step 1: Replace models/__init__.py exports**

Replace the entire contents of `app/models/__init__.py` with brain model exports. Keep old model imports temporarily (commented or behind a flag) since the migration needs both old and new tables to exist simultaneously during data transfer.

```python
# app/models/__init__.py
from app.models.brain import (
    EntityEdge,
    EntityNode,
    KnowledgeEdge,
    KnowledgeNode,
    TopicProfile,
)

# Retained standalone tables
from app.models.asset import Asset
from app.models.publishing_connection import AppConnection, PublishingDestination

__all__ = [
    "TopicProfile",
    "EntityNode",
    "KnowledgeNode",
    "EntityEdge",
    "KnowledgeEdge",
    "Asset",
    "AppConnection",
    "PublishingDestination",
]
```

- [ ] **Step 2: Update alembic/env.py**

Replace the model imports to reference brain models:

```python
# alembic/env.py
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.database import Base

# Brain models
from app.models.brain import (  # noqa: F401
    EntityEdge,
    EntityNode,
    KnowledgeEdge,
    KnowledgeNode,
    TopicProfile,
)

# Retained tables
from app.models.asset import Asset  # noqa: F401
from app.models.publishing_connection import (  # noqa: F401
    AppConnection,
    PublishingDestination,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_settings().database_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_settings().database_url
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, version_table_pk=False)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Commit**

```bash
git add app/models/__init__.py alembic/env.py
git commit -m "feat: update model exports and alembic env for brain schema"
```

---

## Task 4: Write Alembic Migration

This migration creates the brain tables and inserts the marketing topic profile. Data migration from old tables will be handled as a separate script since the old model code is being removed from the codebase — migrating live production data requires the old tables to still exist in the database, which they will until the migration explicitly drops them.

**Files:**
- Create: `alembic/versions/20260409_brain_schema_migration.py`

- [ ] **Step 1: Generate migration scaffold**

Run: `cd /Users/elliot18/Desktop/Home/Projects/ntangible_marketing && python3 -m alembic revision -m "brain_schema_migration"`

- [ ] **Step 2: Write the migration**

The migration creates brain tables. It does NOT drop old tables yet — that happens in a follow-up migration after data is confirmed migrated. This is safer for production.

```python
# alembic/versions/20260409_brain_schema_migration.py
"""brain_schema_migration

Revision ID: <auto-generated>
Revises: <previous-head>
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260409_brain"
down_revision = None  # Will be set by alembic revision command
branch_labels = None
depends_on = None


def upgrade() -> None:
    # topic_profiles
    op.create_table(
        "topic_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("topic_key", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        sa.Column("priority", sa.String(32), server_default="high", nullable=False),
        sa.Column("keywords", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("context_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        sa.Column("intelligence_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        sa.Column("memory_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        sa.Column("config", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_key"),
    )

    # entity_nodes
    op.create_table(
        "entity_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("canonical_name", sa.String(256), nullable=False),
        sa.Column("slug", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("primary_topic_key", sa.String(64), nullable=True),
        sa.Column("search_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "slug", name="uq_entity_type_slug"),
    )
    op.create_index("ix_entity_type_status", "entity_nodes", ["entity_type", "status"])
    op.create_index("ix_entity_topic", "entity_nodes", ["primary_topic_key"])

    # knowledge_nodes
    op.create_table(
        "knowledge_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("primary_topic_key", sa.String(64), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("trust_score", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_latest", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        sa.Column("search_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_kind_status", "knowledge_nodes", ["kind", "status"])
    op.create_index("ix_knowledge_topic", "knowledge_nodes", ["primary_topic_key"])
    op.create_index("ix_knowledge_scheduler", "knowledge_nodes", ["status", "valid_from"])
    op.create_index("ix_knowledge_latest", "knowledge_nodes", ["kind", "status", "is_latest"])

    # entity_edges
    op.create_table(
        "entity_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("relation", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entity_edge_source", "entity_edges", ["source_id"])
    op.create_index("ix_entity_edge_target", "entity_edges", ["target_id"])
    op.create_index("ix_entity_edge_source_rel", "entity_edges", ["source_id", "relation"])
    op.create_index("ix_entity_edge_target_rel", "entity_edges", ["target_id", "relation"])

    # knowledge_edges
    op.create_table(
        "knowledge_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_edge_source", "knowledge_edges", ["source_id"])
    op.create_index("ix_knowledge_edge_target", "knowledge_edges", ["target_id"])
    op.create_index("ix_knowledge_edge_source_rel", "knowledge_edges", ["source_id", "relation"])

    # Seed marketing topic
    op.execute(
        """
        INSERT INTO topic_profiles (topic_key, display_name, description, priority, keywords, config)
        VALUES (
            'marketing',
            'Marketing',
            'Strategy, content, campaigns, posts, and publishing.',
            'critical',
            '["marketing", "content", "social", "brand", "campaign", "publish"]'::jsonb,
            '{}'::jsonb
        )
        """
    )


def downgrade() -> None:
    op.drop_table("knowledge_edges")
    op.drop_table("entity_edges")
    op.drop_table("knowledge_nodes")
    op.drop_table("entity_nodes")
    op.drop_table("topic_profiles")
```

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/20260409_brain_schema_migration.py
git commit -m "feat: add alembic migration for brain schema tables"
```

---

## Task 5: Update Review Queue Service

The most complex service — handles draft listing, review actions, and publishing.

**Files:**
- Modify: `app/services/review_queue.py`
- Test: `tests/test_review_queue.py`

- [ ] **Step 1: Rewrite review_queue.py**

```python
# app/services/review_queue.py
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.brain import EntityEdge, EntityNode, KnowledgeNode
from app.publishers import get_publisher
from app.publishers.blog_factory import get_blog_publisher
from app.publishers.instagram_factory import get_instagram_publisher
from app.services.brain_query import BrainQuery
from app.services.publishing_connection_service import PublishingConnectionService

logger = logging.getLogger(__name__)


# Valid state transitions: action -> (expected_from, target_state)
VALID_TRANSITIONS = {
    "post_now": ("review_required", "publishing"),
    "schedule": ("review_required", "scheduled"),
    "reject": ("review_required", "rejected"),
    "expire": ("review_required", "expired"),
    "pause": ("scheduled", "review_required"),
    "move_to_manual": ("scheduled", "review_required"),
}


class ReviewQueue:
    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)

    def list_manual(self, limit: int = 50) -> list[KnowledgeNode]:
        return self.bq.list_drafts_by_status("review_required", limit=limit)

    def list_automatic(self, limit: int = 50) -> list[KnowledgeNode]:
        return (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.kind == "draft",
                KnowledgeNode.status == "scheduled",
                KnowledgeNode.metadata_.op("->>")("mode") == "automatic",
            )
            .order_by(KnowledgeNode.valid_from.asc())
            .limit(limit)
            .all()
        )

    def list_by_state(self, status: str, limit: int = 50) -> list[KnowledgeNode]:
        return self.bq.list_drafts_by_status(status, limit=limit)

    def get_draft_detail(self, draft_id: uuid.UUID) -> dict | None:
        draft = self.bq.get_knowledge_node(draft_id)
        if not draft:
            return None
        workflow = self.bq.get_workflow_for_draft(draft_id)
        return {"draft": draft, "workflow": workflow}

    def act(
        self,
        draft_id: uuid.UUID,
        action: str,
        actor: str,
        notes: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> KnowledgeNode:
        draft = self.bq.get_knowledge_node(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        if action not in VALID_TRANSITIONS:
            raise ValueError(f"Unknown action: {action}")

        expected_from, target_state = VALID_TRANSITIONS[action]
        if draft.status != expected_from:
            raise ValueError(
                f"Cannot {action} draft in state {draft.status}; "
                f"expected {expected_from}"
            )

        # Record the review action as a knowledge node
        review_node = self.bq.create_knowledge_node(
            kind="review_action",
            title=f"{action} by {actor}",
            content=notes,
            status="active",
            confidence=1.0,
            trust_score=1.0,
            metadata={
                "action": action,
                "actor": actor,
                "notes": notes,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            },
        )
        self.bq.create_edge(
            source_id=draft.id,
            target_id=review_node.id,
            source_type="knowledge",
            target_type="knowledge",
            relation="reviewed_by",
        )

        # Apply state transition
        draft.status = target_state

        if action == "schedule":
            if not scheduled_at:
                raise ValueError("scheduled_at is required for schedule action")
            draft.valid_from = scheduled_at

        if action == "post_now":
            self._publish_draft(draft, published_via="post_now")

        self.db.flush()
        return draft

    def publish_due_draft(self, draft_id: uuid.UUID, actor: str = "scheduler") -> KnowledgeNode:
        draft = self.bq.get_knowledge_node(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")
        if draft.status not in ("scheduled",):
            raise ValueError(f"Cannot publish due draft in state {draft.status}")

        published_via = (
            "automatic_workflow"
            if draft.metadata_.get("mode") == "automatic"
            else "scheduled_manual"
        )

        review_node = self.bq.create_knowledge_node(
            kind="review_action",
            title=f"post_now by {actor}",
            status="active",
            confidence=1.0,
            trust_score=1.0,
            metadata={"action": "post_now", "actor": actor, "notes": "Published by scheduler."},
        )
        self.bq.create_edge(
            source_id=draft.id,
            target_id=review_node.id,
            source_type="knowledge",
            target_type="knowledge",
            relation="reviewed_by",
        )

        draft.status = "publishing"
        self._publish_draft(draft, published_via=published_via)
        self.db.flush()
        return draft

    def _publish_draft(self, draft: KnowledgeNode, *, published_via: str | None = None) -> None:
        meta = dict(draft.metadata_)
        meta["publish_attempted_at"] = datetime.now(timezone.utc).isoformat()
        if published_via:
            meta["published_via"] = published_via

        platform = meta.get("platform", "")
        target = PublishingConnectionService(self.db).resolve_active_publish_target(platform)
        runtime_config = None
        if target is not None:
            runtime_config = {
                **dict(target.get("credentials") or {}),
                **dict(target.get("config") or {}),
            }

        if platform == "blog":
            # Look for linked blog_article knowledge node
            blog_edges = (
                self.db.query(EntityEdge)
                .filter(
                    EntityEdge.source_id == draft.id,
                    EntityEdge.relation == "has_article",
                )
                .all()
            )
            blog_node = None
            if blog_edges:
                blog_node = self.bq.get_knowledge_node(blog_edges[0].target_id)

            payload = dict(meta.get("compliance_result") or {})
            if blog_node:
                bm = blog_node.metadata_
                payload = {
                    "title": blog_node.title,
                    "slug": bm.get("slug", ""),
                    "meta_description": bm.get("meta_description", ""),
                    "body_html": bm.get("body_html", ""),
                    "target_keywords": bm.get("target_keywords", []),
                    "headings": bm.get("headings", []),
                    "audience": bm.get("audience", ""),
                    "topic": bm.get("topic", ""),
                    "angle": bm.get("angle"),
                    "excerpt": bm.get("excerpt"),
                }

            result = get_blog_publisher(runtime_config=runtime_config).publish_article(
                title=payload.get("title", ""),
                slug=payload.get("slug", ""),
                body_markdown=draft.content or "",
                body_html=payload.get("body_html", ""),
                meta_description=payload.get("meta_description", ""),
                target_keywords=payload.get("target_keywords", []),
                headings=payload.get("headings", []),
                audience=payload.get("audience", ""),
                topic=payload.get("topic", ""),
                angle=payload.get("angle"),
                excerpt=payload.get("excerpt"),
            )
            if result.success:
                draft.status = "active"
                meta["platform_post_id"] = result.article_id
                meta["post_url"] = result.url
                meta["published_at"] = (result.published_at or datetime.now(timezone.utc)).isoformat()
                meta.pop("failure_reason", None)
                if blog_node:
                    bm = dict(blog_node.metadata_)
                    bm["cms_provider"] = os.getenv("BLOG_PUBLISHER", "mock").lower()
                    bm["cms_article_id"] = result.article_id
                    bm["canonical_url"] = result.url
                    blog_node.status = "active"
                    blog_node.metadata_ = bm
                self._record_publication(draft, meta)
            else:
                draft.status = "failed"
                meta["failure_reason"] = result.error
                if blog_node:
                    blog_node.status = "failed"
                    bm = dict(blog_node.metadata_)
                    bm["failure_reason"] = result.error
                    blog_node.metadata_ = bm
            draft.metadata_ = meta
            return

        if platform == "instagram":
            from app.models.asset import Asset
            from app.services.instagram_pipeline import build_instagram_caption

            assets = (
                self.db.query(Asset)
                .filter(Asset.draft_variant_id == draft.id)
                .order_by(Asset.sort_order.asc())
                .all()
            )
            asset_urls = [a.url or a.storage_path for a in assets if a.url or a.storage_path]
            if not asset_urls:
                draft.status = "failed"
                meta["failure_reason"] = "Instagram draft requires rendered assets before publish"
                draft.metadata_ = meta
                return

            publish_mode = "feed"
            cr = meta.get("compliance_result")
            if isinstance(cr, dict):
                publish_mode = cr.get("publish_mode", publish_mode)
            hashtags = meta.get("hashtags", [])
            result = get_instagram_publisher(runtime_config=runtime_config).publish_post(
                build_instagram_caption(draft.content or "", hashtags),
                asset_urls,
                publish_mode=publish_mode,
            )
            if result.success:
                draft.status = "active"
                meta["platform_post_id"] = result.post_id
                meta["post_url"] = result.post_url
                meta["published_at"] = datetime.now(timezone.utc).isoformat()
                meta.pop("failure_reason", None)
                self._record_publication(draft, meta)
            else:
                draft.status = "failed"
                meta["failure_reason"] = result.error
            draft.metadata_ = meta
            return

        # Generic publisher (X, LinkedIn, Newsletter)
        publisher = get_publisher(platform=platform, runtime_config=runtime_config)
        publish_metadata = None
        if platform == "newsletter" and isinstance(meta.get("compliance_result"), dict):
            cr = meta["compliance_result"]
            publish_metadata = {
                "subject": cr.get("subject"),
                "preview_text": cr.get("preview_text"),
                "segment": cr.get("segment"),
                "body_html": cr.get("body_html"),
            }
        if publish_metadata is None:
            result = publisher.publish(draft.content or "")
        else:
            result = publisher.publish(draft.content or "", metadata=publish_metadata)

        if result.success:
            draft.status = "active"
            meta["platform_post_id"] = result.platform_post_id
            meta["post_url"] = result.post_url
            meta["published_at"] = datetime.now(timezone.utc).isoformat()
            meta.pop("failure_reason", None)
            self._record_publication(draft, meta)
        else:
            draft.status = "failed"
            meta["failure_reason"] = result.error
        draft.metadata_ = meta

    def _record_publication(self, draft: KnowledgeNode, meta: dict) -> None:
        pub_node = self.bq.create_knowledge_node(
            kind="metric",
            title=f"Publication: {draft.title}",
            status="active",
            confidence=1.0,
            trust_score=1.0,
            metadata={
                "metric_type": "publication",
                "platform": meta.get("platform"),
                "platform_post_id": meta.get("platform_post_id"),
                "post_url": meta.get("post_url"),
                "published_at": meta.get("published_at"),
            },
        )
        self.bq.create_edge(
            source_id=draft.id,
            target_id=pub_node.id,
            source_type="knowledge",
            target_type="knowledge",
            relation="published_as",
        )
```

- [ ] **Step 2: Update tests/test_review_queue.py**

Update the test file to use brain models instead of old models. The test patterns stay the same — create draft nodes, call review queue methods, assert state changes. Replace `DraftVariant` creation with `KnowledgeNode` creation, replace `DraftState.MANUAL_READY` with `"review_required"`, etc.

Key test cases to maintain:
- `test_list_manual` — creates drafts with `status="review_required"`, verifies they appear
- `test_act_post_now` — verifies state goes from `review_required` to `publishing`/`active`
- `test_act_schedule` — verifies `valid_from` gets set
- `test_act_reject` — verifies state goes to `rejected`
- `test_act_invalid_transition` — verifies error on wrong state
- `test_publish_due_draft` — verifies scheduled draft publishes

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest tests/test_review_queue.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/services/review_queue.py tests/test_review_queue.py
git commit -m "feat: update review queue to use brain schema"
```

---

## Task 6: Update Scheduler Service

**Files:**
- Modify: `app/services/scheduler.py`
- Test: `tests/test_scheduler.py`

- [ ] **Step 1: Rewrite scheduler.py**

```python
# app/services/scheduler.py
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.brain import EntityNode, KnowledgeNode
from app.services.brain_query import BrainQuery
from app.services.review_queue import ReviewQueue
from app.services.trigger_engine import TriggerEngine
from app.services.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)

CLAIM_TIMEOUT = timedelta(minutes=15)


@dataclass(frozen=True)
class SchedulerTickResult:
    calendar_rules_fired: int
    manual_drafts_expired: int
    drafts_published: int
    workflow_failures: int = 0


class SchedulerService:
    def __init__(self, db: Session, *, batch_limit: int = 50, worker_name: str = "scheduler"):
        self.db = db
        self.bq = BrainQuery(db)
        self.batch_limit = batch_limit
        self.worker_name = worker_name

    def tick(self, now: datetime | None = None) -> SchedulerTickResult:
        now = now or datetime.now(timezone.utc)
        fired_result = self.fire_due_calendar_rules(now)
        published_result = self.publish_due_drafts(now)
        fired, generation_failures = self._normalize_result(fired_result)
        published, publish_failures = self._normalize_result(published_result)
        expired = self.expire_due_manual_drafts(now)
        return SchedulerTickResult(
            calendar_rules_fired=fired,
            manual_drafts_expired=expired,
            drafts_published=published,
            workflow_failures=generation_failures + publish_failures,
        )

    def run_cycle(self, now: datetime | None = None) -> dict[str, int]:
        result = self.tick(now)
        return {
            "calendar_rules_fired": result.calendar_rules_fired,
            "manual_drafts_expired": result.manual_drafts_expired,
            "drafts_published": result.drafts_published,
            "workflow_failures": result.workflow_failures,
        }

    def _normalize_result(self, result: int | tuple[int, int]) -> tuple[int, int]:
        if isinstance(result, tuple):
            return result
        return result, 0

    def fire_due_calendar_rules(self, now: datetime) -> tuple[int, int]:
        rules = self.bq.list_due_schedule_rules(now, limit=self.batch_limit)
        # Filter to rules whose next_fire_at has passed and are not claimed
        due_rules = []
        for rule in rules:
            next_fire = rule.metadata_.get("next_fire_at")
            if not next_fire:
                continue
            next_fire_dt = datetime.fromisoformat(next_fire)
            if next_fire_dt > now:
                continue
            claimed_at_str = rule.metadata_.get("claimed_at")
            if claimed_at_str:
                claimed_at = datetime.fromisoformat(claimed_at_str)
                if claimed_at > now - CLAIM_TIMEOUT:
                    continue
            # Check workflow is enabled
            wf_id = rule.metadata_.get("workflow_entity_id")
            if wf_id:
                wf = self.bq.get_entity(wf_id if isinstance(wf_id, type(None)) else __import__("uuid").UUID(wf_id))
                if wf and (wf.status != "active" or wf.metadata_.get("enabled") is False):
                    continue
                if wf and wf.metadata_.get("paused_at"):
                    continue
            due_rules.append(rule)

        if not due_rules:
            return 0, 0

        trigger_engine = TriggerEngine(self.db)
        workflow_engine = WorkflowEngine(self.db)
        fired = 0
        failures = 0
        for rule in due_rules:
            if not self._claim_rule(rule, now):
                continue
            wf_id = rule.metadata_.get("workflow_entity_id")
            workflow = self.bq.get_entity(__import__("uuid").UUID(wf_id)) if wf_id else None
            try:
                trigger_event = trigger_engine.fire_schedule_rule(rule)
                logger.info(
                    "Schedule rule %s fired for workflow %s",
                    rule.id,
                    workflow.slug if workflow else wf_id,
                )
                job = workflow_engine.execute(trigger_event)
                meta = dict(rule.metadata_)
                meta["last_fired_at"] = now.isoformat()
                meta["next_fire_at"] = self._advance_next_fire(rule, now).isoformat()
                meta.pop("claimed_at", None)
                meta.pop("claimed_by", None)
                rule.metadata_ = meta
                if workflow is not None:
                    wm = dict(workflow.metadata_)
                    wm["last_run_at"] = now.isoformat()
                    if job.status == "failed":
                        wm["health_status"] = "unhealthy"
                        wm["last_error"] = job.error_message
                        failures += 1
                    else:
                        wm["health_status"] = "healthy"
                        wm["last_success_at"] = now.isoformat()
                        wm.pop("last_error", None)
                    workflow.metadata_ = wm
                fired += 1
            except Exception as exc:
                logger.exception("Schedule rule %s failed", rule.id)
                meta = dict(rule.metadata_)
                meta["last_fired_at"] = now.isoformat()
                meta["next_fire_at"] = self._advance_next_fire(rule, now).isoformat()
                meta.pop("claimed_at", None)
                meta.pop("claimed_by", None)
                rule.metadata_ = meta
                if workflow is not None:
                    wm = dict(workflow.metadata_)
                    wm["last_run_at"] = now.isoformat()
                    wm["health_status"] = "unhealthy"
                    wm["last_error"] = str(exc)
                    workflow.metadata_ = wm
                fired += 1
                failures += 1
        self.db.flush()
        return fired, failures

    def expire_due_manual_drafts(self, now: datetime) -> int:
        drafts = self.bq.list_expirable_drafts(now, limit=self.batch_limit)
        if not drafts:
            return 0

        queue = ReviewQueue(self.db)
        for draft in drafts:
            queue.act(
                draft_id=draft.id,
                action="expire",
                actor="scheduler",
                notes="Expired at end of manual review day.",
            )
        self.db.flush()
        return len(drafts)

    def publish_due_drafts(self, now: datetime) -> tuple[int, int]:
        due_drafts = self.bq.list_publishable_drafts(now, limit=self.batch_limit)
        if not due_drafts:
            return 0, 0

        queue = ReviewQueue(self.db)
        published = 0
        failures = 0
        for draft in due_drafts:
            try:
                logger.info(
                    "Publishing due draft %s (platform=%s, status=%s)",
                    draft.id, draft.metadata_.get("platform"), draft.status,
                )
                queue.publish_due_draft(draft.id, actor="scheduler")
                self._update_workflow_health_for_draft(draft, now)
                if draft.status == "active":
                    logger.info("Draft %s published successfully", draft.id)
                elif draft.status == "failed":
                    logger.warning("Draft %s publish failed: %s", draft.id, draft.metadata_.get("failure_reason"))
                    failures += 1
                published += 1
            except Exception as exc:
                logger.exception("Failed to publish draft %s", draft.id)
                failures += 1
                published += 1
        self.db.flush()
        return published, failures

    def _claim_rule(self, rule: KnowledgeNode, now: datetime) -> bool:
        claimed_at_str = rule.metadata_.get("claimed_at")
        if claimed_at_str:
            claimed_at = datetime.fromisoformat(claimed_at_str)
            if claimed_at > now - CLAIM_TIMEOUT:
                return False
        meta = dict(rule.metadata_)
        meta["claimed_at"] = now.isoformat()
        meta["claimed_by"] = self.worker_name
        rule.metadata_ = meta
        self.db.flush()
        return True

    def _update_workflow_health_for_draft(self, draft: KnowledgeNode, now: datetime) -> None:
        workflow = self.bq.get_workflow_for_draft(draft.id)
        if workflow is None:
            return
        wm = dict(workflow.metadata_)
        wm["last_run_at"] = now.isoformat()
        if draft.status == "active":
            wm["last_success_at"] = now.isoformat()
            wm["health_status"] = "healthy"
            wm.pop("last_error", None)
        elif draft.status == "failed":
            wm["health_status"] = "unhealthy"
            wm["last_error"] = draft.metadata_.get("failure_reason")
        workflow.metadata_ = wm

    def _advance_next_fire(self, rule: KnowledgeNode, now: datetime) -> datetime:
        meta = rule.metadata_
        cron = meta.get("cron_expression", "0 9 * * *")
        fields = cron.split()
        if len(fields) != 5:
            return now + timedelta(days=1)

        minute_field, hour_field, _day_field, _month_field, weekday_field = fields
        minute = int(minute_field) if minute_field.isdigit() else 0
        hour = int(hour_field) if hour_field.isdigit() else 9
        timezone_name = meta.get("timezone", "America/New_York")
        tz = ZoneInfo(timezone_name)
        local_now = now.astimezone(tz)
        next_local = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_local <= local_now:
            next_local += timedelta(days=1)

        if weekday_field != "*" and weekday_field.isdigit():
            target_weekday = int(weekday_field)
            python_weekday = (target_weekday - 1) % 7
            while next_local.weekday() != python_weekday:
                next_local += timedelta(days=1)

        return next_local.astimezone(timezone.utc)


def run_scheduler_loop(db_factory, *, interval_seconds: int = 15) -> None:
    while True:
        db = db_factory()
        try:
            summary = SchedulerService(db).run_cycle()
            db.commit()
            if any(summary.values()):
                logger.info("Scheduler cycle completed: %s", summary)
        except Exception:
            logger.exception("Scheduler cycle failed")
            db.rollback()
        finally:
            db.close()
        time.sleep(interval_seconds)
```

- [ ] **Step 2: Update tests/test_scheduler.py for brain models**

Same test patterns: create schedule_rule knowledge nodes and draft knowledge nodes, verify the scheduler fires/publishes/expires them correctly.

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest tests/test_scheduler.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/services/scheduler.py tests/test_scheduler.py
git commit -m "feat: update scheduler to use brain schema"
```

---

## Task 7: Update Trigger Engine and Workflow Engine

**Files:**
- Modify: `app/services/trigger_engine.py`
- Modify: `app/services/workflow_engine.py`
- Test: `tests/test_trigger_engine.py`

- [ ] **Step 1: Update trigger_engine.py**

The trigger engine creates trigger knowledge nodes instead of TriggerEvent rows. Add a `fire_schedule_rule` method that takes a KnowledgeNode (schedule_rule) instead of CalendarRule.

Key changes:
- `fire_calendar_rule(rule: CalendarRule)` → `fire_schedule_rule(rule: KnowledgeNode)` — creates a `kind='trigger'` knowledge node, links it to the workflow entity via edge
- `ingest_external(payload, workflow_id)` → `ingest_external(payload, workflow_slug)` — looks up workflow entity by slug
- Return the trigger KnowledgeNode instead of TriggerEvent

- [ ] **Step 2: Update workflow_engine.py**

Key changes:
- `resolve_workflow(trigger)` — follows the edge from trigger to workflow entity instead of looking up by `trigger.workflow_id`
- `get_active_version(workflow)` — reads the linked `workflow_config` knowledge node (edge: workflow → workflow_config, relation: `has_config`)
- `execute(trigger)` — creates draft KnowledgeNode, links it to trigger and workflow via edges

- [ ] **Step 3: Update and run tests**

Run: `python3 -m pytest tests/test_trigger_engine.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/services/trigger_engine.py app/services/workflow_engine.py tests/test_trigger_engine.py
git commit -m "feat: update trigger and workflow engines for brain schema"
```

---

## Task 8: Update Pipeline Services (X, LinkedIn, Instagram, Blog)

Each pipeline service follows the same pattern: generate content → compliance check → create record → publish. Update each to create KnowledgeNodes instead of platform-specific models.

**Files:**
- Modify: `app/services/x_pipeline.py`
- Modify: `app/services/linkedin_pipeline.py`
- Modify: `app/services/instagram_pipeline.py`
- Modify: `app/services/blog_service.py`
- Tests: `tests/test_x_pipeline.py`, `tests/test_linkedin_pipeline.py`, `tests/test_instagram_pipeline.py`, `tests/test_blog_service.py`

- [ ] **Step 1: Update x_pipeline.py**

Replace `ContentQueue` creation with `KnowledgeNode(kind='draft')` creation. Replace `GenerationLog` with `KnowledgeNode(kind='generation_log')`. Link them with an edge. Replace status enum checks with string status checks.

```python
# app/services/x_pipeline.py — key changes
from app.models.brain import KnowledgeNode
from app.services.brain_query import BrainQuery

def generate_partner_x_item(request_data: dict, db: Session) -> KnowledgeNode:
    bq = BrainQuery(db)
    variations, log_data = generate_tweets(...)
    # ... compliance check same as before ...

    draft = bq.create_draft(
        title=f"X post: {selected_variation['content'][:50]}",
        content=selected_compliance.corrected_content or selected_variation["content"],
        platform="x",
        intent=selected_variation.get("intent", "partner"),
        pillar=request_data["pillar"],
        hashtags=selected_compliance.corrected_hashtags or [],
        mode="manual",
        status="pending",
        extra_metadata={
            "content_type": request_data["content_type"],
            "request_payload": request_data,
            "compliance_result": {"passed": True, "checks_run": selected_compliance.checks_run},
        },
    )
    bq.create_knowledge_node(
        kind="generation_log",
        title=f"Gen log for {draft.id}",
        status="active",
        metadata={**log_data, "draft_id": str(draft.id)},
    )
    db.commit()
    return publish_partner_x_item(draft.id, db)

def publish_partner_x_item(content_id, db: Session) -> KnowledgeNode:
    bq = BrainQuery(db)
    item = bq.get_knowledge_node(content_id)
    # ... same publish logic, using item.metadata_ for platform fields ...
```

- [ ] **Step 2: Update linkedin_pipeline.py, instagram_pipeline.py, blog_service.py**

Same pattern as x_pipeline: replace model-specific classes with KnowledgeNode + BrainQuery. Each pipeline creates draft nodes with platform-specific metadata.

- [ ] **Step 3: Update and run pipeline tests**

Run: `python3 -m pytest tests/test_x_pipeline.py tests/test_linkedin_pipeline.py tests/test_instagram_pipeline.py tests/test_blog_service.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/services/x_pipeline.py app/services/linkedin_pipeline.py app/services/instagram_pipeline.py app/services/blog_service.py tests/test_x_pipeline.py tests/test_linkedin_pipeline.py tests/test_instagram_pipeline.py tests/test_blog_service.py
git commit -m "feat: update pipeline services for brain schema"
```

---

## Task 9: Update Secondary Services

All secondary services follow the same conversion pattern: replace model-specific queries with BrainQuery calls, replace model-specific objects with EntityNode/KnowledgeNode.

**Files:** All remaining service files in `app/services/`

- [ ] **Step 1: Update each service**

For each service, the pattern is:
1. Replace model imports with `from app.models.brain import EntityNode, KnowledgeNode`
2. Replace `from app.services.brain_query import BrainQuery`
3. Replace `db.query(OldModel)` with `bq.list_entities_by_type("type")` or `bq.list_knowledge_by_kind("kind")`
4. Replace attribute access (e.g., `campaign.name`) with `entity.canonical_name` or `entity.metadata_["field"]`

Services to update:
- `campaign_service.py` — campaigns are `entity_type='campaign'`, runs are `kind='run'`
- `competitor_service.py` — competitors are `entity_type='competitor'`, observations are `kind='observation'`, signals are `kind='signal'`
- `lead_nurture_service.py` — leads are `entity_type='lead'`, contacts are `entity_type='contact'`, tasks are `kind='nurture_task'`
- `partner_intake_service.py` — partner_sources are `entity_type='partner_source'`, events are `kind='trigger'`
- `partner_delivery_service.py` — bundles are `kind='delivery_package'`
- `revenue_service.py` — playbooks are `entity_type='playbook'`, goals are `kind='goal'`, conversions are `kind='conversion'`
- `sports_calendar_service.py` — events are `entity_type='sports_event'`, runs are `kind='run'`
- `repurposing_service.py` — sources are `kind='reference_content'`, derivatives are `kind='draft'`
- `ugc_service.py` — requests are `kind='outreach'`, submissions are `kind='submission'`
- `video_service.py` — briefs are `kind='video_brief'`
- `science_content_service.py` — records are `kind='reference_content'`
- `prompt_assembler.py` — reads knowledge nodes for context
- `memory_retrieval.py` — reads observation/reference_content nodes
- `workflow_editor.py` — reads/writes workflow entities and workflow_config nodes
- `automatic_control.py` — reads workflow entities
- `platform_generation.py` — creates draft nodes
- `analytics_ingest.py` — creates metric nodes
- `publishing_connection_service.py` — reads publishing_channel entities

- [ ] **Step 2: Update all secondary service tests**

Run: `python3 -m pytest tests/ -v --ignore=tests/test_brain_models.py --ignore=tests/test_brain_query.py`
Expected: PASS (or identify remaining failures)

- [ ] **Step 3: Commit**

```bash
git add app/services/ tests/
git commit -m "feat: update all secondary services for brain schema"
```

---

## Task 10: Update Routes

The routes file (`app/web/routes.py`) has ~50 data loader functions. Each needs to be updated to query brain tables.

**Files:**
- Modify: `app/web/routes.py`

- [ ] **Step 1: Update route data loaders**

The key pattern for each loader:
- Replace `db.query(OldModel)` with `BrainQuery(db)` calls
- Replace enum comparisons with string comparisons
- Return the same dict shape so templates don't need changes

Example — `load_manual_cards`:

**Before:**
```python
def load_manual_cards(db: Session, limit: int = 50):
    drafts = ReviewQueue(db).list_manual(limit=limit)
    return [_serialize_card(db, d) for d in drafts]
```

**After:**
```python
def load_manual_cards(db: Session, limit: int = 50):
    drafts = ReviewQueue(db).list_manual(limit=limit)
    return [_serialize_brain_card(db, d) for d in drafts]
```

Where `_serialize_brain_card` reads from `KnowledgeNode.metadata_` instead of `DraftVariant` attributes:

```python
def _serialize_brain_card(db: Session, draft: KnowledgeNode) -> dict:
    meta = draft.metadata_
    bq = BrainQuery(db)
    workflow = bq.get_workflow_for_draft(draft.id)
    return {
        "id": str(draft.id),
        "content": draft.content,
        "platform": meta.get("platform", ""),
        "intent": meta.get("intent", ""),
        "pillar": meta.get("pillar", ""),
        "hashtags": meta.get("hashtags", []),
        "state": draft.status,
        "created_at": draft.created_at,
        "scheduled_publish_at": draft.valid_from,
        "expires_at": draft.valid_until,
        "workflow_name": workflow.canonical_name if workflow else "Unknown",
        "workflow_slug": workflow.slug if workflow else "",
        "compliance_result": meta.get("compliance_result"),
        "platform_post_id": meta.get("platform_post_id"),
        "post_url": meta.get("post_url"),
        "published_at": meta.get("published_at"),
        "failure_reason": meta.get("failure_reason"),
    }
```

Apply same pattern to all loaders. The templates receive the same dict keys they always have.

- [ ] **Step 2: Update action handlers**

`apply_web_action` now calls `ReviewQueue.act()` with string actions instead of enum values (already done in Task 5).

- [ ] **Step 3: Add graph view route**

```python
@router.get("/control-room/graph")
async def graph_view(request: Request, db: Session = Depends(get_db)):
    user = _require_auth(request, db)
    bq = BrainQuery(db)
    graph_data = bq.get_graph_data(topic_key="marketing")
    nodes = []
    for e in graph_data["entities"]:
        nodes.append({"id": str(e.id), "label": e.canonical_name, "type": e.entity_type, "group": "entity"})
    for k in graph_data["knowledge"]:
        nodes.append({"id": str(k.id), "label": k.title, "type": k.kind, "group": "knowledge"})
    links = []
    for edge in graph_data["entity_edges"]:
        links.append({"source": str(edge.source_id), "target": str(edge.target_id), "relation": edge.relation})
    for edge in graph_data["knowledge_edges"]:
        links.append({"source": str(edge.source_id), "target": str(edge.target_id), "relation": edge.relation})
    return templates.TemplateResponse("graph.html", {
        "request": request, "user": user, "nodes_json": json.dumps(nodes), "links_json": json.dumps(links),
    })
```

- [ ] **Step 4: Run route tests**

Run: `python3 -m pytest tests/test_web_*.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/web/routes.py
git commit -m "feat: update all routes for brain schema, add graph view"
```

---

## Task 11: Create Graph View Template

**Files:**
- Create: `app/web/templates/graph.html`

- [ ] **Step 1: Create graph template**

A simple force-directed graph using d3.js (loaded from CDN). Renders entity nodes as circles, knowledge nodes as squares, edges as lines. Click a node to see its details.

```html
{% extends "base.html" %}
{% block title %}Knowledge Graph{% endblock %}
{% block content %}
<div class="container-fluid">
  <h2>Marketing Knowledge Graph</h2>
  <div id="graph-container" style="width:100%;height:80vh;border:1px solid var(--bs-border-color);border-radius:8px;"></div>
</div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
  const nodes = {{ nodes_json | safe }};
  const links = {{ links_json | safe }};
  const container = document.getElementById('graph-container');
  const width = container.clientWidth;
  const height = container.clientHeight;

  const svg = d3.select('#graph-container').append('svg')
    .attr('width', width).attr('height', height);

  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2));

  const link = svg.append('g').selectAll('line').data(links).join('line')
    .attr('stroke', '#999').attr('stroke-opacity', 0.6);

  const node = svg.append('g').selectAll('g').data(nodes).join('g')
    .call(d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended));

  node.each(function(d) {
    const el = d3.select(this);
    if (d.group === 'entity') {
      el.append('circle').attr('r', 8).attr('fill', '#60a5fa');
    } else {
      el.append('rect').attr('width', 12).attr('height', 12).attr('x', -6).attr('y', -6).attr('fill', '#4ade80');
    }
  });

  node.append('title').text(d => `${d.type}: ${d.label}`);
  node.append('text').attr('dx', 12).attr('dy', 4).text(d => d.label).style('font-size', '11px');

  simulation.on('tick', () => {
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  function dragstarted(event) { if (!event.active) simulation.alphaTarget(0.3).restart(); event.subject.fx = event.subject.x; event.subject.fy = event.subject.y; }
  function dragged(event) { event.subject.fx = event.x; event.subject.fy = event.y; }
  function dragended(event) { if (!event.active) simulation.alphaTarget(0); event.subject.fx = null; event.subject.fy = null; }
</script>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add app/web/templates/graph.html
git commit -m "feat: add knowledge graph visualization template"
```

---

## Task 12: Remove Old Model Files

After all services and routes are updated, remove the old model files that are no longer imported anywhere.

**Files:**
- Delete: `app/models/content.py`, `app/models/linkedin.py`, `app/models/workflow.py`, `app/models/review.py`, `app/models/trigger.py`, `app/models/campaign.py`, `app/models/competitor.py`, `app/models/lead.py`, `app/models/partner.py`, `app/models/revenue.py`, `app/models/sports.py`, `app/models/science.py`, `app/models/repurposing.py`, `app/models/video.py`, `app/models/ugc.py`, `app/models/blog.py`, `app/models/content_brain.py`, `app/models/memory.py`, `app/models/analytics.py`, `app/models/instagram.py`

- [ ] **Step 1: Verify no imports remain**

Run: `grep -r "from app.models.content import\|from app.models.linkedin import\|from app.models.workflow import\|from app.models.review import\|from app.models.trigger import" app/ --include="*.py"`
Expected: No results (all imports replaced with brain model imports)

- [ ] **Step 2: Delete old model files**

```bash
rm app/models/content.py app/models/linkedin.py app/models/workflow.py app/models/review.py app/models/trigger.py app/models/campaign.py app/models/competitor.py app/models/lead.py app/models/partner.py app/models/revenue.py app/models/sports.py app/models/science.py app/models/repurposing.py app/models/video.py app/models/ugc.py app/models/blog.py app/models/content_brain.py app/models/memory.py app/models/analytics.py app/models/instagram.py
```

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old model files replaced by brain schema"
```

---

## Task 13: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Verify alembic migration works**

Run: `python3 -m alembic upgrade head` (against a test database)
Expected: Migration applies cleanly, brain tables created, marketing topic seeded

- [ ] **Step 3: Verify app starts**

Run: `python3 -m uvicorn app.main:app --reload` (or however the app starts)
Expected: App starts without import errors

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete brain schema migration — marketing as brain topic"
```
