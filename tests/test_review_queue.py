"""Tests for app/services/review_queue.py using the brain schema.

Uses an in-memory SQLite database.  Postgres-specific types are patched so
SQLite can create the tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

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
from app.publishers.base import PostResult  # noqa: E402
from app.publishers.blog_base import BlogPublishResult  # noqa: E402
from app.services.review_queue import VALID_TRANSITIONS, ReviewQueue  # noqa: E402

# ---------------------------------------------------------------------------
# Tables needed for these tests
# ---------------------------------------------------------------------------
BRAIN_TABLES = [
    EntityNode.__table__,
    KnowledgeNode.__table__,
    EntityEdge.__table__,
    KnowledgeEdge.__table__,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def _make_draft_node(db, status: str = "review_required", platform: str = "x", **kwargs) -> KnowledgeNode:
    """Helper: create and persist a draft KnowledgeNode."""
    node = KnowledgeNode(
        id=uuid.uuid4(),
        kind="draft",
        title="Test draft",
        content="Test content",
        status=status,
        confidence=0.8,
        trust_score=0.8,
        metadata_={"platform": platform, "hashtags": [], "mode": "manual", **kwargs.pop("metadata_", {})},
        **kwargs,
    )
    db.add(node)
    db.flush()
    return node


# ---------------------------------------------------------------------------
# VALID_TRANSITIONS structure
# ---------------------------------------------------------------------------


def test_valid_transitions_defined():
    """All expected actions have defined transitions."""
    assert "post_now" in VALID_TRANSITIONS
    assert "schedule" in VALID_TRANSITIONS
    assert "reject" in VALID_TRANSITIONS
    assert "expire" in VALID_TRANSITIONS
    assert "pause" in VALID_TRANSITIONS
    assert "move_to_manual" in VALID_TRANSITIONS


# ---------------------------------------------------------------------------
# list_manual
# ---------------------------------------------------------------------------


def test_list_manual(db):
    """list_manual returns drafts with status='review_required'."""
    _make_draft_node(db, status="review_required")
    _make_draft_node(db, status="review_required")
    _make_draft_node(db, status="scheduled")  # should NOT appear

    queue = ReviewQueue(db)
    results = queue.list_manual()

    assert len(results) == 2
    assert all(r.status == "review_required" for r in results)


# ---------------------------------------------------------------------------
# list_automatic
# ---------------------------------------------------------------------------


def test_list_automatic(db):
    """list_automatic returns drafts with status='scheduled'."""
    _make_draft_node(db, status="scheduled")
    _make_draft_node(db, status="scheduled")
    _make_draft_node(db, status="review_required")  # should NOT appear

    queue = ReviewQueue(db)
    results = queue.list_automatic()

    assert len(results) == 2
    assert all(r.status == "scheduled" for r in results)


# ---------------------------------------------------------------------------
# act — schedule
# ---------------------------------------------------------------------------


def test_act_schedule(db):
    """act('schedule') sets valid_from and transitions to 'scheduled'."""
    draft = _make_draft_node(db, status="review_required")
    scheduled_time = datetime.now(timezone.utc) + timedelta(hours=2)

    queue = ReviewQueue(db)
    result = queue.act(
        draft_id=draft.id,
        action="schedule",
        actor="boss",
        scheduled_at=scheduled_time,
    )

    assert result.status == "scheduled"
    # valid_from may be stored as naive UTC in SQLite; compare timestamps
    assert result.valid_from is not None


def test_act_schedule_without_time_raises(db):
    """act('schedule') raises ValueError when scheduled_at is not provided."""
    draft = _make_draft_node(db, status="review_required")

    queue = ReviewQueue(db)
    with pytest.raises(ValueError, match="scheduled_at is required"):
        queue.act(draft_id=draft.id, action="schedule", actor="boss")


# ---------------------------------------------------------------------------
# act — reject
# ---------------------------------------------------------------------------


def test_act_reject(db):
    """act('reject') transitions draft to 'rejected'."""
    draft = _make_draft_node(db, status="review_required")

    queue = ReviewQueue(db)
    result = queue.act(draft_id=draft.id, action="reject", actor="boss", notes="Off-brand")

    assert result.status == "rejected"


# ---------------------------------------------------------------------------
# act — expire
# ---------------------------------------------------------------------------


def test_act_expire(db):
    """act('expire') transitions draft to 'expired'."""
    draft = _make_draft_node(db, status="review_required")

    queue = ReviewQueue(db)
    result = queue.act(draft_id=draft.id, action="expire", actor="system")

    assert result.status == "expired"


# ---------------------------------------------------------------------------
# act — invalid transition
# ---------------------------------------------------------------------------


def test_act_invalid_transition(db):
    """act raises ValueError when the draft is in the wrong state."""
    draft = _make_draft_node(db, status="rejected")

    queue = ReviewQueue(db)
    with pytest.raises(ValueError, match="Cannot reject draft in state rejected"):
        queue.act(draft_id=draft.id, action="reject", actor="boss")


def test_act_unknown_action_raises(db):
    """act raises ValueError for an unrecognised action string."""
    draft = _make_draft_node(db, status="review_required")

    queue = ReviewQueue(db)
    with pytest.raises(ValueError, match="Unknown action"):
        queue.act(draft_id=draft.id, action="teleport", actor="boss")


def test_act_draft_not_found(db):
    """act raises ValueError when draft_id does not exist."""
    queue = ReviewQueue(db)
    with pytest.raises(ValueError, match="not found"):
        queue.act(draft_id=uuid.uuid4(), action="reject", actor="boss")


# ---------------------------------------------------------------------------
# get_draft_detail
# ---------------------------------------------------------------------------


def test_get_draft_detail(db):
    """get_draft_detail returns a dict with 'draft' key."""
    draft = _make_draft_node(db, status="review_required")

    queue = ReviewQueue(db)
    detail = queue.get_draft_detail(draft.id)

    assert detail is not None
    assert detail["draft"].id == draft.id
    assert "workflow" in detail


def test_get_draft_detail_not_found(db):
    """get_draft_detail returns None for unknown id."""
    queue = ReviewQueue(db)
    assert queue.get_draft_detail(uuid.uuid4()) is None


# ---------------------------------------------------------------------------
# publish_due_draft
# ---------------------------------------------------------------------------


@patch("app.services.review_queue.PublishingConnectionService")
@patch("app.services.review_queue.get_publisher")
def test_publish_due_draft_success(mock_get_pub, mock_pcs, db):
    """publish_due_draft publishes and sets status to 'active'."""
    mock_pub = MagicMock()
    mock_pub.publish.return_value = PostResult(
        success=True,
        platform_post_id="xyz999",
        post_url="https://x.com/i/status/xyz999",
        posted_at=datetime.now(timezone.utc).isoformat(),
    )
    mock_get_pub.return_value = mock_pub
    mock_pcs.return_value.resolve_active_publish_target.return_value = None

    draft = _make_draft_node(db, status="scheduled", platform="x")

    queue = ReviewQueue(db)
    result = queue.publish_due_draft(draft.id, actor="scheduler")

    assert result.status == "active"


def test_publish_due_draft_wrong_status(db):
    """publish_due_draft raises ValueError for a non-scheduled draft."""
    draft = _make_draft_node(db, status="review_required")

    queue = ReviewQueue(db)
    with pytest.raises(ValueError, match="Cannot publish due draft in state"):
        queue.publish_due_draft(draft.id)


# ---------------------------------------------------------------------------
# act post_now (generic publisher path)
# ---------------------------------------------------------------------------


@patch("app.services.review_queue.PublishingConnectionService")
@patch("app.services.review_queue.get_publisher")
def test_act_post_now_success(mock_get_pub, mock_pcs, db):
    """act('post_now') publishes the draft and sets status to 'active'."""
    mock_pub = MagicMock()
    mock_pub.publish.return_value = PostResult(
        success=True,
        platform_post_id="abc123",
        post_url="https://x.com/i/status/abc123",
        posted_at=datetime.now(timezone.utc).isoformat(),
    )
    mock_get_pub.return_value = mock_pub
    mock_pcs.return_value.resolve_active_publish_target.return_value = None

    draft = _make_draft_node(db, status="review_required", platform="x")

    queue = ReviewQueue(db)
    result = queue.act(draft_id=draft.id, action="post_now", actor="boss")

    assert result.status == "active"
    assert result.metadata_.get("platform_post_id") == "abc123"


@patch("app.services.review_queue.PublishingConnectionService")
@patch("app.services.review_queue.get_publisher")
def test_act_post_now_failure(mock_get_pub, mock_pcs, db):
    """act('post_now') sets status to 'failed' when publish fails."""
    mock_pub = MagicMock()
    mock_pub.publish.return_value = PostResult(success=False, error="Rate limited")
    mock_get_pub.return_value = mock_pub
    mock_pcs.return_value.resolve_active_publish_target.return_value = None

    draft = _make_draft_node(db, status="review_required", platform="x")

    queue = ReviewQueue(db)
    result = queue.act(draft_id=draft.id, action="post_now", actor="boss")

    assert result.status == "failed"
    assert result.metadata_.get("failure_reason") == "Rate limited"


# ---------------------------------------------------------------------------
# pause
# ---------------------------------------------------------------------------


def test_act_pause(db):
    """act('pause') transitions a scheduled draft back to 'review_required'."""
    draft = _make_draft_node(db, status="scheduled")

    queue = ReviewQueue(db)
    result = queue.act(draft_id=draft.id, action="pause", actor="boss")

    assert result.status == "review_required"
