"""Tests for app/services/brain_query.py using an in-memory SQLite database.

JSONB operator filtering (metadata->>'platform') is Postgres-only and is not
exercised in these tests.  The suite focuses on the structural behaviour of
every BrainQuery method.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Patch Postgres-specific types so SQLite can create the tables
# ---------------------------------------------------------------------------
SQLiteTypeCompiler.visit_TSVECTOR = lambda self, type_, **kw: "TEXT"  # type: ignore[attr-defined]
SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "TEXT"  # type: ignore[attr-defined]
SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "TEXT"  # type: ignore[attr-defined]

from app.database import Base  # noqa: E402
from app.models.brain import EntityEdge, EntityNode, KnowledgeEdge, KnowledgeNode  # noqa: E402
from app.services.brain_query import BrainQuery  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BRAIN_TABLES = [
    EntityNode.__table__,
    KnowledgeNode.__table__,
    EntityEdge.__table__,
    KnowledgeEdge.__table__,
]


@pytest.fixture()
def db():
    """Provide a fresh in-memory SQLite session for each test."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=BRAIN_TABLES)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=BRAIN_TABLES)
        engine.dispose()


@pytest.fixture()
def bq(db):
    return BrainQuery(db)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_draft(db, *, status: str = "pending", **kwargs) -> KnowledgeNode:
    node = KnowledgeNode(
        id=uuid.uuid4(),
        kind="draft",
        title=kwargs.pop("title", "A draft"),
        content=kwargs.pop("content", "body"),
        status=status,
        metadata_=kwargs.pop("metadata_", {}),
        **kwargs,
    )
    db.add(node)
    db.flush()
    return node


def _make_entity(db, *, entity_type: str = "workflow", slug: str | None = None, **kwargs) -> EntityNode:
    node = EntityNode(
        id=uuid.uuid4(),
        entity_type=entity_type,
        canonical_name=kwargs.pop("canonical_name", "Test Entity"),
        slug=slug or f"slug-{uuid.uuid4().hex[:8]}",
        status=kwargs.pop("status", "active"),
        **kwargs,
    )
    db.add(node)
    db.flush()
    return node


# ---------------------------------------------------------------------------
# Knowledge node tests
# ---------------------------------------------------------------------------

def test_list_drafts_by_status(db, bq):
    _make_draft(db, status="pending")
    _make_draft(db, status="pending")
    _make_draft(db, status="scheduled")

    results = bq.list_drafts_by_status("pending")

    assert len(results) == 2
    assert all(n.kind == "draft" for n in results)
    assert all(n.status == "pending" for n in results)


def test_list_drafts_by_status_empty(db, bq):
    _make_draft(db, status="scheduled")

    results = bq.list_drafts_by_status("pending")

    assert results == []


def test_list_publishable_drafts(db, bq):
    now = _now()
    past = now - timedelta(hours=1)
    future = now + timedelta(hours=1)

    # Should be returned: scheduled + valid_from in the past
    ready = KnowledgeNode(
        id=uuid.uuid4(),
        kind="draft",
        title="Ready",
        status="scheduled",
        valid_from=past,
        metadata_={},
    )
    # Should NOT be returned: scheduled but valid_from in the future
    not_yet = KnowledgeNode(
        id=uuid.uuid4(),
        kind="draft",
        title="Not yet",
        status="scheduled",
        valid_from=future,
        metadata_={},
    )
    # Should NOT be returned: wrong status
    wrong_status = KnowledgeNode(
        id=uuid.uuid4(),
        kind="draft",
        title="Wrong status",
        status="pending",
        valid_from=past,
        metadata_={},
    )
    db.add_all([ready, not_yet, wrong_status])
    db.flush()

    results = bq.list_publishable_drafts(now)

    assert len(results) == 1
    assert results[0].id == ready.id


def test_list_expirable_drafts(db, bq):
    now = _now()
    past = now - timedelta(hours=1)
    future = now + timedelta(hours=1)

    # Should be returned
    expirable = KnowledgeNode(
        id=uuid.uuid4(),
        kind="draft",
        title="Expirable",
        status="review_required",
        valid_until=past,
        metadata_={},
    )
    # valid_until still in the future — not yet expirable
    not_expired = KnowledgeNode(
        id=uuid.uuid4(),
        kind="draft",
        title="Not expired",
        status="review_required",
        valid_until=future,
        metadata_={},
    )
    db.add_all([expirable, not_expired])
    db.flush()

    results = bq.list_expirable_drafts(now)

    assert len(results) == 1
    assert results[0].id == expirable.id


def test_list_due_schedule_rules(db, bq):
    active_rule = KnowledgeNode(
        id=uuid.uuid4(),
        kind="schedule_rule",
        title="Weekly LinkedIn",
        status="active",
        metadata_={"next_fire_at": "2026-04-10T08:00:00Z"},
    )
    inactive_rule = KnowledgeNode(
        id=uuid.uuid4(),
        kind="schedule_rule",
        title="Paused rule",
        status="inactive",
        metadata_={},
    )
    db.add_all([active_rule, inactive_rule])
    db.flush()

    results = bq.list_due_schedule_rules(_now())

    assert len(results) == 1
    assert results[0].id == active_rule.id


def test_create_draft_node(db, bq):
    node = bq.create_draft(
        title="Launch post",
        content="We're live!",
        platform="linkedin",
        intent="brand",
        pillar="thought_leadership",
        hashtags=["#launch"],
        status="pending",
    )

    assert node.id is not None
    assert node.kind == "draft"
    assert node.title == "Launch post"
    assert node.primary_topic_key == "marketing"
    assert node.status == "pending"
    assert node.metadata_["platform"] == "linkedin"
    assert node.metadata_["hashtags"] == ["#launch"]

    # Verify persisted
    fetched = bq.get_knowledge_node(node.id)
    assert fetched is not None
    assert fetched.title == "Launch post"


# ---------------------------------------------------------------------------
# Entity node tests
# ---------------------------------------------------------------------------

def test_list_entities_by_type(db, bq):
    _make_entity(db, entity_type="workflow")
    _make_entity(db, entity_type="workflow")
    _make_entity(db, entity_type="platform")

    results = bq.list_entities_by_type("workflow")

    assert len(results) == 2
    assert all(e.entity_type == "workflow" for e in results)


def test_get_entity_by_slug(db, bq):
    target = _make_entity(db, entity_type="workflow", slug="monday-linkedin")
    _make_entity(db, entity_type="workflow", slug="tuesday-x")

    found = bq.get_entity_by_slug("workflow", "monday-linkedin")

    assert found is not None
    assert found.id == target.id

    missing = bq.get_entity_by_slug("workflow", "does-not-exist")
    assert missing is None


def test_get_entity_by_slug_different_type(db, bq):
    _make_entity(db, entity_type="platform", slug="linkedin")

    # Same slug but wrong type should return None
    result = bq.get_entity_by_slug("workflow", "linkedin")
    assert result is None


# ---------------------------------------------------------------------------
# Edge tests
# ---------------------------------------------------------------------------

def test_create_edge(db, bq):
    entity = _make_entity(db)
    draft = _make_draft(db)

    edge = bq.create_edge(
        source_id=entity.id,
        target_id=draft.id,
        source_type="entity",
        target_type="knowledge",
        relation="produced",
        confidence=0.9,
    )

    assert edge.id is not None
    assert edge.source_id == entity.id
    assert edge.target_id == draft.id
    assert edge.relation == "produced"
    assert edge.confidence == 0.9


def test_get_edges_from(db, bq):
    entity = _make_entity(db)
    draft1 = _make_draft(db)
    draft2 = _make_draft(db)
    other_entity = _make_entity(db)

    bq.create_edge(
        source_id=entity.id,
        target_id=draft1.id,
        source_type="entity",
        target_type="knowledge",
        relation="produced",
    )
    bq.create_edge(
        source_id=entity.id,
        target_id=draft2.id,
        source_type="entity",
        target_type="knowledge",
        relation="produced",
    )
    # Edge from a different entity — should not appear
    bq.create_edge(
        source_id=other_entity.id,
        target_id=draft1.id,
        source_type="entity",
        target_type="knowledge",
        relation="produced",
    )

    edges = bq.get_edges_from(entity.id)
    assert len(edges) == 2
    assert all(e.source_id == entity.id for e in edges)

    # Filter by relation
    filtered = bq.get_edges_from(entity.id, relation="produced")
    assert len(filtered) == 2

    none_found = bq.get_edges_from(entity.id, relation="reviewed_by")
    assert none_found == []


def test_get_workflow_for_draft(db, bq):
    workflow = _make_entity(db, entity_type="workflow", slug="wf-linkedin")
    draft = _make_draft(db)

    bq.create_edge(
        source_id=workflow.id,
        target_id=draft.id,
        source_type="entity",
        target_type="knowledge",
        relation="produced",
    )

    result = bq.get_workflow_for_draft(draft.id)

    assert result is not None
    assert result.id == workflow.id
    assert result.entity_type == "workflow"


def test_get_workflow_for_draft_no_edge(db, bq):
    draft = _make_draft(db)
    result = bq.get_workflow_for_draft(draft.id)
    assert result is None


def test_get_graph_data_topic_none_returns_all(db, bq):
    """topic_key=None should return all entities and knowledge regardless of topic."""
    e1 = bq.create_entity(entity_type="company", canonical_name="Acme", slug="acme")
    db.flush()
    from sqlalchemy import text as sa_text
    db.execute(sa_text("UPDATE entity_nodes SET primary_topic_key = NULL WHERE id = :id"), {"id": str(e1.id)})

    e2 = bq.create_entity(entity_type="workflow", canonical_name="WF1", slug="wf1")
    db.flush()
    db.execute(sa_text("UPDATE entity_nodes SET primary_topic_key = 'marketing' WHERE id = :id"), {"id": str(e2.id)})

    k1 = bq.create_knowledge_node(kind="fact", title="Fact1", content="test", status="active")
    db.flush()
    db.execute(sa_text("UPDATE knowledge_nodes SET primary_topic_key = 'work' WHERE id = :id"), {"id": str(k1.id)})

    db.flush()

    data = bq.get_graph_data(topic_key=None)
    entity_ids = {e.id for e in data["entities"]}
    knowledge_ids = {k.id for k in data["knowledge"]}

    assert e1.id in entity_ids
    assert e2.id in entity_ids
    assert k1.id in knowledge_ids
