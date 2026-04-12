"""Tests for brain-native methods on TriggerEngine.

Uses an in-memory SQLite database — Postgres-specific types are patched out.
"""

from __future__ import annotations

import uuid

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
from app.services.trigger_engine import TriggerEngine  # noqa: E402

BRAIN_TABLES = [
    EntityNode.__table__,
    KnowledgeNode.__table__,
    EntityEdge.__table__,
    KnowledgeEdge.__table__,
]


@pytest.fixture()
def db():
    """Fresh in-memory SQLite session per test."""
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


def test_fire_schedule_rule_creates_trigger_node(db):
    """fire_schedule_rule should produce a KnowledgeNode with kind='trigger'."""
    bq = BrainQuery(db)
    workflow_entity_id = str(uuid.uuid4())

    rule = bq.create_knowledge_node(
        kind="schedule_rule",
        title="Daily LinkedIn post",
        status="active",
        confidence=1.0,
        trust_score=1.0,
        metadata={
            "cron_expression": "0 9 * * 1-5",
            "timezone": "America/Chicago",
            "publish_hour_local": 9,
            "publish_minute_local": 0,
            "workflow_entity_id": workflow_entity_id,
        },
    )
    db.flush()

    engine = TriggerEngine(db)
    trigger_node = engine.fire_schedule_rule(rule)

    assert trigger_node.kind == "trigger"
    assert trigger_node.status == "active"
    assert trigger_node.metadata_["trigger_type"] == "calendar"
    assert trigger_node.metadata_["rule_id"] == str(rule.id)
    assert trigger_node.metadata_["cron_expression"] == "0 9 * * 1-5"
    assert trigger_node.metadata_["timezone"] == "America/Chicago"
    assert trigger_node.metadata_["publish_hour_local"] == 9
    assert trigger_node.metadata_["workflow_entity_id"] == workflow_entity_id
    assert "fired_at" in trigger_node.metadata_
    assert "Schedule trigger:" in trigger_node.title

    # Confirm the node is persisted in the session
    found = db.query(KnowledgeNode).filter(KnowledgeNode.id == trigger_node.id).first()
    assert found is not None


def test_create_manual_trigger(db):
    """create_manual_trigger should produce a KnowledgeNode with kind='trigger'."""
    workflow_entity_id = str(uuid.uuid4())
    request_text = "Write a post about our spring camp registration opening"

    engine = TriggerEngine(db)
    trigger_node = engine.create_manual_trigger(request_text, workflow_entity_id)

    assert trigger_node.kind == "trigger"
    assert trigger_node.status == "active"
    assert trigger_node.metadata_["trigger_type"] == "manual"
    assert trigger_node.metadata_["request"] == request_text
    assert trigger_node.metadata_["workflow_entity_id"] == workflow_entity_id
    assert "Manual trigger:" in trigger_node.title

    found = db.query(KnowledgeNode).filter(KnowledgeNode.id == trigger_node.id).first()
    assert found is not None
