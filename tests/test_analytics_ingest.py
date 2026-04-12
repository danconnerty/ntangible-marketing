import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models.brain import KnowledgeNode
from app.models.review import ContentJob, DraftVariant
from app.models.workflow import DraftState, Platform
from app.services.analytics_ingest import (
    calculate_workflow_rollup,
    record_publication,
    score_content_metrics,
)


def _make_job() -> ContentJob:
    return ContentJob(
        id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        workflow_version_id=uuid.uuid4(),
        trigger_event_id=uuid.uuid4(),
        prompt_snapshot={"system": "sys", "user": "usr"},
        status="manual_ready",
    )


def _make_draft(job: ContentJob, state: DraftState = DraftState.PUBLISHED) -> DraftVariant:
    return DraftVariant(
        id=uuid.uuid4(),
        content_job_id=job.id,
        platform=Platform.X,
        content="Pressure data beats vibes.",
        hashtags=["#MentalPerformance"],
        state=state,
        timezone="America/New_York",
        platform_post_id="post-123" if state == DraftState.PUBLISHED else None,
        post_url="https://example.com/post-123" if state == DraftState.PUBLISHED else None,
        published_at=datetime.now(timezone.utc) if state == DraftState.PUBLISHED else None,
    )


def _make_metric_node(metric_type: str, extra_meta: dict | None = None) -> KnowledgeNode:
    meta = {"metric_type": metric_type}
    if extra_meta:
        meta.update(extra_meta)
    node = KnowledgeNode(
        id=uuid.uuid4(),
        kind="metric",
        title=f"{metric_type}:test",
        status="active",
        metadata_=meta,
    )
    return node


def test_record_publication_returns_none_for_knowledge_node():
    """record_publication is a no-op when draft is already a KnowledgeNode."""
    draft_node = KnowledgeNode(
        id=uuid.uuid4(),
        kind="draft",
        title="test draft",
        status="published",
        metadata_={"platform": "x"},
    )
    db = MagicMock()
    result = record_publication(db, draft=draft_node, publish_result={"success": True})
    assert result is None
    db.add.assert_not_called()


def test_record_publication_creates_metric_node_for_draft_variant():
    """record_publication creates a KnowledgeNode(kind='metric') for a DraftVariant."""
    job = _make_job()
    draft = _make_draft(job)
    db = MagicMock()

    def query_side_effect(model):
        query = MagicMock()
        if model is ContentJob:
            query.filter.return_value.first.return_value = job
        return query

    db.query.side_effect = query_side_effect

    with patch("app.services.analytics_ingest.BrainQuery") as MockBQ:
        mock_bq = MockBQ.return_value
        expected_node = _make_metric_node("publication")
        mock_bq.create_knowledge_node.return_value = expected_node

        result = record_publication(
            db,
            draft=draft,
            publish_result={"success": True, "platform_post_id": "post-123"},
        )

    assert result is expected_node
    mock_bq.create_knowledge_node.assert_called_once()
    call_kwargs = mock_bq.create_knowledge_node.call_args[1]
    assert call_kwargs["kind"] == "metric"
    assert call_kwargs["metadata"]["metric_type"] == "publication"
    assert call_kwargs["metadata"]["workflow_id"] == str(job.workflow_id)
    assert call_kwargs["metadata"]["platform"] == Platform.X.value


def test_record_publication_skips_when_job_missing():
    """record_publication returns None if the ContentJob cannot be found."""
    job = _make_job()
    draft = _make_draft(job)
    db = MagicMock()

    def query_side_effect(model):
        query = MagicMock()
        if model is ContentJob:
            query.filter.return_value.first.return_value = None
        return query

    db.query.side_effect = query_side_effect
    result = record_publication(db, draft=draft, publish_result={"success": True})
    assert result is None


def test_calculate_workflow_rollup_uses_review_outcomes_and_engagement():
    published_job = _make_job()
    rejected_job = _make_job()
    expired_job = _make_job()

    drafts = [
        _make_draft(published_job, state=DraftState.PUBLISHED),
        _make_draft(rejected_job, state=DraftState.REJECTED),
        _make_draft(expired_job, state=DraftState.EXPIRED),
    ]

    # Use KnowledgeNode objects as publications (brain schema)
    pub_node = _make_metric_node(
        "publication",
        {
            "draft_variant_id": str(drafts[0].id),
            "platform": "x",
            "workflow_id": str(published_job.workflow_id),
        },
    )

    # Snapshot as a KnowledgeNode with metrics nested inside metadata_
    snap_node = _make_metric_node(
        "analytics_snapshot",
        {
            "publication_node_id": str(pub_node.id),
            "metrics": {"impressions": 5000, "engagements": 400, "engagement_rate": 0.08},
        },
    )

    rollup = calculate_workflow_rollup(
        drafts=drafts,
        publications=[pub_node],
        snapshots=[snap_node],
        workflow=SimpleNamespace(
            id=published_job.workflow_id,
            name="Tuesday X Data Drop",
            slug="tuesday-x-data-drop",
        ),
        platform=Platform.X,
        trigger_type="calendar",
        window_days=30,
    )

    assert rollup["approval_rate"] == 1 / 3
    assert rollup["rejection_rate"] == 1 / 3
    assert rollup["expiration_rate"] == 1 / 3
    assert rollup["publication_success_rate"] == 1 / 3
    assert rollup["engagement_percentile"] == 0.08
    assert rollup["promotion_confidence"] > 0


def test_score_content_metrics_flags_recycle_candidates():
    scored = score_content_metrics(
        Platform.LINKEDIN,
        {
            "impressions": 10000,
            "engagements": 800,
            "comments": 45,
            "shares": 30,
            "clicks": 120,
        },
    )

    assert scored["content_score"] >= 75
    assert scored["recycle_recommended"] is True
    assert scored["score_label"] in {"strong", "excellent"}


def test_calculate_workflow_rollup_with_empty_inputs():
    """Rollup returns zero-rate dict when no drafts or publications."""
    workflow = SimpleNamespace(id=uuid.uuid4(), name="Empty Workflow", slug="empty")
    rollup = calculate_workflow_rollup(
        drafts=[],
        publications=[],
        snapshots=[],
        workflow=workflow,
        platform=Platform.LINKEDIN,
        trigger_type=None,
        window_days=30,
    )
    assert rollup["approval_rate"] == 0.0
    assert rollup["publication_success_rate"] == 0.0
    assert rollup["engagement_percentile"] == 0.0
    assert rollup["promotion_confidence"] > 0  # base confidence even with no data
    assert rollup["record_count"] == 0
