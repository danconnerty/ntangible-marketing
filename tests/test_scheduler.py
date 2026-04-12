"""Tests for app/services/scheduler.py using an in-memory SQLite database."""

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
from app.services.scheduler import SchedulerService  # noqa: E402

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


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_draft(db, *, status: str = "pending", valid_from=None, valid_until=None, **kwargs) -> KnowledgeNode:
    node = KnowledgeNode(
        id=uuid.uuid4(),
        kind="draft",
        title=kwargs.pop("title", "A draft"),
        content=kwargs.pop("content", "body"),
        status=status,
        valid_from=valid_from,
        valid_until=valid_until,
        metadata_=kwargs.pop("metadata_", {"platform": "linkedin"}),
        **kwargs,
    )
    db.add(node)
    db.flush()
    return node


def _make_schedule_rule(db, *, status: str = "active", next_fire_at: datetime | None = None, cron: str = "0 9 * * *", **kwargs) -> KnowledgeNode:
    meta = {
        "cron_expression": cron,
        "timezone": "America/New_York",
    }
    if next_fire_at is not None:
        meta["next_fire_at"] = next_fire_at.isoformat()
    meta.update(kwargs.pop("extra_meta", {}))
    node = KnowledgeNode(
        id=uuid.uuid4(),
        kind="schedule_rule",
        title="Test schedule rule",
        status=status,
        metadata_=meta,
    )
    db.add(node)
    db.flush()
    return node


# ---------------------------------------------------------------------------
# Test: expire_due_manual_drafts
# ---------------------------------------------------------------------------

def test_expire_due_manual_drafts(db):
    now = _now()
    past = now - timedelta(minutes=5)

    # This draft should be expired: status=review_required, valid_until=past
    draft = _make_draft(db, status="review_required", valid_until=past)
    # This one should NOT be expired: valid_until is in the future
    _make_draft(db, status="review_required", valid_until=now + timedelta(hours=1))
    # This one should NOT be expired: wrong status
    _make_draft(db, status="scheduled", valid_until=past)

    scheduler = SchedulerService(db)
    count = scheduler.expire_due_manual_drafts(now)

    assert count == 1
    db.refresh(draft)
    assert draft.status == "expired"


# ---------------------------------------------------------------------------
# Test: publish_due_drafts calls ReviewQueue
# ---------------------------------------------------------------------------

def test_publish_due_drafts_calls_review_queue(db):
    now = _now()
    past = now - timedelta(minutes=5)

    draft = _make_draft(db, status="scheduled", valid_from=past)

    scheduler = SchedulerService(db)
    with patch("app.services.scheduler.ReviewQueue") as queue_cls:
        mock_queue = queue_cls.return_value
        mock_queue.publish_due_draft.return_value = None
        scheduler._update_workflow_health_for_draft = MagicMock()
        published, failures = scheduler.publish_due_drafts(now)

    assert published == 1
    mock_queue.publish_due_draft.assert_called_once_with(draft.id, actor="scheduler")


# ---------------------------------------------------------------------------
# Test: fire_due_calendar_rules with no rules returns (0, 0)
# ---------------------------------------------------------------------------

def test_fire_due_calendar_rules_no_rules(db):
    now = _now()
    scheduler = SchedulerService(db)
    fired, failures = scheduler.fire_due_calendar_rules(now)
    assert fired == 0
    assert failures == 0


# ---------------------------------------------------------------------------
# Test: fire_due_calendar_rules skips rules with no next_fire_at or future fire time
# ---------------------------------------------------------------------------

def test_fire_due_calendar_rules_skips_future_rules(db):
    now = _now()
    future = now + timedelta(hours=1)
    # Rule with next_fire_at in the future — should not fire
    _make_schedule_rule(db, next_fire_at=future)

    scheduler = SchedulerService(db)
    fired, failures = scheduler.fire_due_calendar_rules(now)
    assert fired == 0
    assert failures == 0


# ---------------------------------------------------------------------------
# Test: _advance_next_fire returns correct next time
# ---------------------------------------------------------------------------

def test_advance_next_fire(db):
    now = datetime(2026, 4, 9, 14, 0, tzinfo=timezone.utc)  # 10 AM ET (UTC-4 in April)

    rule = _make_schedule_rule(db, cron="30 9 * * *")

    scheduler = SchedulerService(db)
    next_fire = scheduler._advance_next_fire(rule, now)

    # 9:30 AM ET the next day
    assert next_fire > now
    # Convert back to ET to verify hour/minute
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    local_next = next_fire.astimezone(et)
    assert local_next.hour == 9
    assert local_next.minute == 30


# ---------------------------------------------------------------------------
# Test: _claim_rule sets claimed_at in metadata_
# ---------------------------------------------------------------------------

def test_claim_rule(db):
    now = _now()
    rule = _make_schedule_rule(db, next_fire_at=now - timedelta(minutes=1))

    scheduler = SchedulerService(db)
    result = scheduler._claim_rule(rule, now)

    assert result is True
    assert "claimed_at" in rule.metadata_
    assert rule.metadata_["claimed_by"] == "scheduler"
    # Claimed timestamp should be close to now
    claimed_dt = datetime.fromisoformat(rule.metadata_["claimed_at"])
    assert abs((claimed_dt - now).total_seconds()) < 2


def test_claim_rule_already_claimed_recently(db):
    now = _now()
    # Rule claimed just 5 minutes ago — within CLAIM_TIMEOUT (15 min)
    recent_claim = (now - timedelta(minutes=5)).isoformat()
    rule = _make_schedule_rule(
        db,
        next_fire_at=now - timedelta(minutes=1),
        extra_meta={"claimed_at": recent_claim, "claimed_by": "other_worker"},
    )

    scheduler = SchedulerService(db)
    result = scheduler._claim_rule(rule, now)

    assert result is False


# ---------------------------------------------------------------------------
# Test: tick returns a SchedulerTickResult
# ---------------------------------------------------------------------------

def test_tick_returns_structured_result(db):
    scheduler = SchedulerService(db)

    with (
        patch.object(scheduler, "fire_due_calendar_rules", return_value=(2, 1)),
        patch.object(scheduler, "expire_due_manual_drafts", return_value=3),
        patch.object(scheduler, "publish_due_drafts", return_value=(4, 2)),
    ):
        result = scheduler.tick(datetime.now(timezone.utc))

    assert result.calendar_rules_fired == 2
    assert result.manual_drafts_expired == 3
    assert result.drafts_published == 4
    assert result.workflow_failures == 3


# ---------------------------------------------------------------------------
# Test: fire_due_calendar_rules fires a rule and advances next_fire_at
# ---------------------------------------------------------------------------

def test_fire_due_calendar_rules_fires_rule(db):
    now = datetime(2026, 4, 9, 14, 0, tzinfo=timezone.utc)
    past = now - timedelta(minutes=1)

    rule = _make_schedule_rule(db, next_fire_at=past, cron="0 9 * * *")

    scheduler = SchedulerService(db)
    with (
        patch("app.services.scheduler.TriggerEngine") as trigger_cls,
        patch("app.services.scheduler.WorkflowEngine") as workflow_cls,
    ):
        mock_trigger = trigger_cls.return_value
        mock_trigger_node = MagicMock()
        mock_trigger.fire_schedule_rule.return_value = mock_trigger_node

        mock_job = MagicMock()
        mock_job.status = "completed"
        mock_job.metadata_ = {}
        workflow_cls.return_value.execute_brain.return_value = mock_job

        fired, failures = scheduler.fire_due_calendar_rules(now)

    assert fired == 1
    assert failures == 0
    mock_trigger.fire_schedule_rule.assert_called_once_with(rule)
    workflow_cls.return_value.execute_brain.assert_called_once_with(mock_trigger_node)
    # next_fire_at should have been advanced
    assert "next_fire_at" in rule.metadata_
    next_fire_dt = datetime.fromisoformat(rule.metadata_["next_fire_at"])
    assert next_fire_dt > now
