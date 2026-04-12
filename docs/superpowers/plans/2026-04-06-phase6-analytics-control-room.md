# Phase 6 Analytics Control Room Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add canonical analytics records, ingestion, rollups, API endpoints, and a real analytics page that fits the existing control-room workflow.

**Architecture:** Extend the canonical control-room data model instead of reusing legacy phase-specific publish tables. Record every control-room publication into durable publication and analytics tables, compute workflow health and promotion-confidence rollups in a service layer, and expose those rollups through both API and the existing `/control-room/analytics` page.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, Jinja2 templates, pytest

---

## File Structure

- Create: `app/models/analytics.py`
  Purpose: canonical analytics tables for publications, snapshots, and workflow metrics.
- Create: `app/services/analytics_ingest.py`
  Purpose: record publication rows, ingest metrics snapshots, and compute analytics rollups for UI/API.
- Create: `app/api/analytics_routes.py`
  Purpose: JSON analytics endpoints for summary, workflow breakdowns, and per-publication snapshot history.
- Create: `tests/test_analytics_ingest.py`
  Purpose: unit tests for publication recording, snapshot ingest, and rollup calculations.
- Modify: `app/models/__init__.py`
  Purpose: register analytics models with metadata imports used elsewhere in tests/app startup.
- Modify: `app/services/review_queue.py`
  Purpose: create a canonical publication record when `post_now` succeeds.
- Modify: `app/web/routes.py`
  Purpose: load analytics data into the `/control-room/analytics` view.
- Modify: `app/web/templates/analytics.html`
  Purpose: replace the placeholder page with grouped analytics summary and confidence details.
- Modify: `app/main.py`
  Purpose: include analytics API routes.
- Modify: `tests/test_control_room_api.py`
  Purpose: verify analytics routes are mounted.
- Modify: `tests/test_review_queue.py`
  Purpose: verify successful publication writes a canonical publication record.
- Create: `tests/test_analytics_api.py`
  Purpose: API and page-level integration tests for analytics responses and rendered content.
- Create: `alembic/versions/20260406_add_phase6_analytics_tables.py`
  Purpose: create analytics tables in Postgres environments.

### Task 1: Add Failing Analytics Model Tests

**Files:**
- Create: `tests/test_analytics_ingest.py`
- Modify: `app/models/__init__.py`

- [ ] **Step 1: Write the failing model and service tests**

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.analytics import AnalyticsSnapshot, PublicationRecord, WorkflowMetric


def test_publication_record_persists_ids_and_platform(session, workflow, workflow_version, trigger_event, content_job, draft_variant):
    record = PublicationRecord(
        id=uuid.uuid4(),
        draft_variant_id=draft_variant.id,
        content_job_id=content_job.id,
        workflow_id=workflow.id,
        workflow_version_id=workflow_version.id,
        trigger_event_id=trigger_event.id,
        platform=draft_variant.platform,
        platform_post_id="post-123",
        post_url="https://example.com/post-123",
        published_at=datetime(2026, 4, 6, tzinfo=UTC),
        publish_result={"success": True},
    )

    session.add(record)
    session.commit()

    saved = session.get(PublicationRecord, record.id)
    assert saved is not None
    assert saved.platform.value == "x"
    assert saved.platform_post_id == "post-123"


def test_analytics_snapshot_links_to_publication(session, publication_record):
    snapshot = AnalyticsSnapshot(
        publication_record_id=publication_record.id,
        metrics={"impressions": 1200, "engagements": 84, "engagement_rate": 0.07},
    )

    session.add(snapshot)
    session.commit()

    saved = session.query(AnalyticsSnapshot).one()
    assert saved.metrics["impressions"] == 1200
    assert saved.publication_record_id == publication_record.id


def test_workflow_metric_stores_promotion_confidence(session, workflow, workflow_version):
    metric = WorkflowMetric(
        workflow_id=workflow.id,
        workflow_version_id=workflow_version.id,
        platform=workflow.platform,
        trigger_type="leaderboard_published",
        window_days=30,
        publication_success_rate=1.0,
        approval_rate=0.75,
        rejection_rate=0.10,
        expiration_rate=0.15,
        engagement_percentile=0.82,
        promotion_confidence=0.78,
        record_count=12,
    )

    session.add(metric)
    session.commit()

    saved = session.query(WorkflowMetric).one()
    assert saved.promotion_confidence == 0.78
    assert saved.record_count == 12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analytics_ingest.py -q`
Expected: FAIL because `app.models.analytics` does not exist yet.

- [ ] **Step 3: Write minimal analytics models**

```python
class PublicationRecord(Base):
    __tablename__ = "publication_records"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_variant_id = mapped_column(UUID(as_uuid=True), ForeignKey("draft_variants.id"), nullable=False)
    content_job_id = mapped_column(UUID(as_uuid=True), ForeignKey("content_jobs.id"), nullable=False)
    workflow_id = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    workflow_version_id = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_versions.id"), nullable=False)
    trigger_event_id = mapped_column(UUID(as_uuid=True), ForeignKey("trigger_events.id"), nullable=True)
    platform = mapped_column(platform_enum, nullable=False)
    platform_post_id = mapped_column(String(128), nullable=True)
    post_url = mapped_column(Text, nullable=True)
    published_at = mapped_column(DateTime(timezone=True), nullable=False)
    publish_result = mapped_column(JSONB, nullable=False, default=dict)
```

```python
class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publication_record_id = mapped_column(
        UUID(as_uuid=True), ForeignKey("publication_records.id"), nullable=False
    )
    captured_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    metrics = mapped_column(JSONB, nullable=False, default=dict)
```

```python
class WorkflowMetric(Base):
    __tablename__ = "workflow_metrics"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    workflow_version_id = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_versions.id"), nullable=True)
    platform = mapped_column(platform_enum, nullable=False)
    trigger_type = mapped_column(String(64), nullable=True)
    window_days = mapped_column(Integer, nullable=False, default=30)
    publication_success_rate = mapped_column(Float, nullable=False, default=0.0)
    approval_rate = mapped_column(Float, nullable=False, default=0.0)
    rejection_rate = mapped_column(Float, nullable=False, default=0.0)
    expiration_rate = mapped_column(Float, nullable=False, default=0.0)
    engagement_percentile = mapped_column(Float, nullable=False, default=0.0)
    promotion_confidence = mapped_column(Float, nullable=False, default=0.0)
    record_count = mapped_column(Integer, nullable=False, default=0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_analytics_ingest.py -q`
Expected: PASS for model persistence cases.

- [ ] **Step 5: Commit**

```bash
git add app/models/analytics.py app/models/__init__.py tests/test_analytics_ingest.py
git commit -m "feat: add canonical analytics models"
```

### Task 2: Add Publication Recording To The Review Workflow

**Files:**
- Modify: `app/services/review_queue.py`
- Modify: `tests/test_review_queue.py`
- Create: `app/services/analytics_ingest.py`

- [ ] **Step 1: Write the failing publish-record test**

```python
def test_post_now_success_creates_publication_record(session, manual_ready_draft, mock_get_pub):
    queue = ReviewQueue(session)

    with patch("app.services.review_queue.get_publisher") as mock_factory:
        mock_factory.return_value.publish.return_value = PublishResult(
            success=True,
            platform_post_id="abc123",
            post_url="https://x.com/post/abc123",
        )
        result = queue.act(
            draft_id=manual_ready_draft.id,
            action=ReviewActionType.POST_NOW,
            actor="admin",
        )

    records = session.query(PublicationRecord).all()
    assert result.state == DraftState.PUBLISHED
    assert len(records) == 1
    assert records[0].draft_variant_id == manual_ready_draft.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_review_queue.py::test_post_now_success_creates_publication_record -q`
Expected: FAIL because no publication record is written.

- [ ] **Step 3: Write minimal publication-record service and call it from publish success paths**

```python
def record_publication(
    db: Session,
    *,
    draft: DraftVariant,
    publish_result: dict,
) -> PublicationRecord:
    job = db.query(ContentJob).filter(ContentJob.id == draft.content_job_id).one()
    record = PublicationRecord(
        draft_variant_id=draft.id,
        content_job_id=job.id,
        workflow_id=job.workflow_id,
        workflow_version_id=job.workflow_version_id,
        trigger_event_id=job.trigger_event_id,
        platform=draft.platform,
        platform_post_id=draft.platform_post_id,
        post_url=draft.post_url,
        published_at=draft.published_at,
        publish_result=publish_result,
    )
    db.add(record)
    db.flush()
    return record
```

```python
if result.success:
    draft.state = DraftState.PUBLISHED
    draft.platform_post_id = result.platform_post_id
    draft.post_url = result.post_url
    draft.published_at = datetime.now(timezone.utc)
    record_publication(
        self.db,
        draft=draft,
        publish_result={
            "success": True,
            "platform_post_id": draft.platform_post_id,
            "post_url": draft.post_url,
        },
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_review_queue.py::test_post_now_success_creates_publication_record -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/review_queue.py app/services/analytics_ingest.py tests/test_review_queue.py
git commit -m "feat: record publications from control room publishes"
```

### Task 3: Add Analytics Snapshot Ingest And Rollup Calculations

**Files:**
- Modify: `app/services/analytics_ingest.py`
- Modify: `tests/test_analytics_ingest.py`

- [ ] **Step 1: Write the failing rollup tests**

```python
def test_ingest_snapshot_and_compute_workflow_metrics(session, publication_record):
    ingest_analytics_snapshot(
        session,
        publication_record_id=publication_record.id,
        metrics={"impressions": 5000, "engagements": 400, "engagement_rate": 0.08},
    )

    summary = compute_workflow_metrics(session, workflow_id=publication_record.workflow_id)

    assert summary["publication_success_rate"] == 1.0
    assert summary["engagement_percentile"] > 0
    assert summary["promotion_confidence"] > 0
```

```python
def test_compute_workflow_metrics_uses_review_outcomes(session, workflow, workflow_version, trigger_event, make_job_and_draft):
    make_job_and_draft(workflow, workflow_version, trigger_event, state=DraftState.MANUAL_READY)
    make_job_and_draft(workflow, workflow_version, trigger_event, state=DraftState.REJECTED)
    make_job_and_draft(workflow, workflow_version, trigger_event, state=DraftState.EXPIRED)

    summary = compute_workflow_metrics(session, workflow_id=workflow.id)

    assert summary["approval_rate"] == 1 / 3
    assert summary["rejection_rate"] == 1 / 3
    assert summary["expiration_rate"] == 1 / 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analytics_ingest.py -q`
Expected: FAIL because ingest and rollup helpers do not exist yet.

- [ ] **Step 3: Write minimal ingest and rollup logic**

```python
def ingest_analytics_snapshot(db: Session, *, publication_record_id: uuid.UUID, metrics: dict) -> AnalyticsSnapshot:
    snapshot = AnalyticsSnapshot(
        publication_record_id=publication_record_id,
        metrics=metrics,
    )
    db.add(snapshot)
    db.flush()
    _refresh_workflow_metric(db, publication_record_id=publication_record_id)
    return snapshot
```

```python
def compute_workflow_metrics(db: Session, *, workflow_id: uuid.UUID, window_days: int = 30) -> dict:
    drafts = (
        db.query(DraftVariant)
        .join(ContentJob, ContentJob.id == DraftVariant.content_job_id)
        .filter(ContentJob.workflow_id == workflow_id)
        .all()
    )
    publications = (
        db.query(PublicationRecord)
        .filter(PublicationRecord.workflow_id == workflow_id)
        .all()
    )
    snapshots = (
        db.query(AnalyticsSnapshot)
        .join(PublicationRecord, PublicationRecord.id == AnalyticsSnapshot.publication_record_id)
        .filter(PublicationRecord.workflow_id == workflow_id)
        .all()
    )
    total = len(drafts) or 1
    approval_rate = sum(1 for draft in drafts if draft.state == DraftState.PUBLISHED) / total
    rejection_rate = sum(1 for draft in drafts if draft.state == DraftState.REJECTED) / total
    expiration_rate = sum(1 for draft in drafts if draft.state == DraftState.EXPIRED) / total
    publication_success_rate = len(publications) / total
    engagement_rates = [float(snapshot.metrics.get("engagement_rate", 0.0)) for snapshot in snapshots]
    engagement_percentile = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0.0
    promotion_confidence = round(
        (publication_success_rate * 0.4) + (approval_rate * 0.2) + (engagement_percentile * 0.4),
        4,
    )
    return {
        "approval_rate": approval_rate,
        "rejection_rate": rejection_rate,
        "expiration_rate": expiration_rate,
        "publication_success_rate": publication_success_rate,
        "engagement_percentile": engagement_percentile,
        "promotion_confidence": promotion_confidence,
        "record_count": len(publications),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_analytics_ingest.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/analytics_ingest.py tests/test_analytics_ingest.py
git commit -m "feat: add analytics snapshot ingest and rollups"
```

### Task 4: Add Analytics API Endpoints

**Files:**
- Create: `app/api/analytics_routes.py`
- Modify: `app/main.py`
- Create: `tests/test_analytics_api.py`
- Modify: `tests/test_control_room_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_analytics_summary_endpoint_returns_rollups(client, db_session, analytics_seed_data):
    response = client.get("/api/analytics/summary", headers={"x-api-key": "test-key"})

    assert response.status_code == 200
    body = response.json()
    assert "summary" in body
    assert "workflow_metrics" in body
```

```python
def test_analytics_publication_detail_endpoint_returns_snapshots(client, publication_record, analytics_snapshot):
    response = client.get(
        f"/api/analytics/publications/{publication_record.id}",
        headers={"x-api-key": "test-key"},
    )

    assert response.status_code == 200
    assert response.json()["snapshots"][0]["metrics"]["impressions"] == 1200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analytics_api.py tests/test_control_room_api.py -q`
Expected: FAIL because analytics routes are not mounted.

- [ ] **Step 3: Write minimal analytics routes and mount them**

```python
router = APIRouter(prefix="/api/analytics", tags=["analytics"], dependencies=[Depends(verify_api_key)])


@router.get("/summary")
def analytics_summary(
    platform: str | None = Query(default=None),
    workflow_slug: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    return build_analytics_summary(db, platform=platform, workflow_slug=workflow_slug, days=days)


@router.get("/publications/{publication_id}")
def analytics_publication_detail(publication_id: str, db: Session = Depends(get_db)):
    detail = get_publication_analytics_detail(db, uuid.UUID(publication_id))
    if not detail:
        raise HTTPException(status_code=404, detail="Publication not found")
    return detail
```

```python
from app.api.analytics_routes import router as analytics_router

app.include_router(analytics_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_analytics_api.py tests/test_control_room_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/analytics_routes.py app/main.py tests/test_analytics_api.py tests/test_control_room_api.py
git commit -m "feat: add analytics api routes"
```

### Task 5: Replace The Placeholder Analytics Page

**Files:**
- Modify: `app/web/routes.py`
- Modify: `app/web/templates/analytics.html`
- Create: `tests/test_web_analytics_view.py`

- [ ] **Step 1: Write the failing page test**

```python
def test_analytics_page_renders_summary_sections(client, analytics_seed_data):
    response = client.get("/control-room/analytics")

    assert response.status_code == 200
    text = response.text
    assert "Promotion confidence" in text
    assert "Workflow health" in text
    assert "By platform" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_analytics_view.py -q`
Expected: FAIL because the page is still a placeholder.

- [ ] **Step 3: Write minimal view loader and template**

```python
@web_router.get("/analytics")
def analytics_view(
    request: Request,
    platform: str | None = None,
    workflow_slug: str | None = None,
    days: int = 30,
    db: Session = Depends(get_db),
):
    summary = build_analytics_summary(db, platform=platform, workflow_slug=workflow_slug, days=days)
    return templates.TemplateResponse(
        request,
        "analytics.html",
        {
            "page": "analytics",
            "summary": summary["summary"],
            "workflow_metrics": summary["workflow_metrics"],
            "platform_metrics": summary["platform_metrics"],
            "filters": summary["filters"],
        },
    )
```

```html
<section class="analytics-grid">
  <article class="metric-card">
    <h2>Promotion confidence</h2>
    <p class="metric-value">{{ "%.0f"|format(summary.promotion_confidence * 100) }}%</p>
  </article>
  <article class="metric-card">
    <h2>Workflow health</h2>
    <p class="text-muted">Approval, rejection, expiration, and publish success rates</p>
  </article>
</section>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_analytics_view.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/web/routes.py app/web/templates/analytics.html tests/test_web_analytics_view.py
git commit -m "feat: add control room analytics page"
```

### Task 6: Add The Alembic Migration And End-To-End Verification

**Files:**
- Create: `alembic/versions/20260406_add_phase6_analytics_tables.py`
- Modify: `tests/conftest.py` if metadata imports need to be extended
- Test: `tests/test_analytics_ingest.py`
- Test: `tests/test_analytics_api.py`
- Test: `tests/test_web_analytics_view.py`
- Test: `tests/test_review_queue.py`

- [ ] **Step 1: Write the migration**

```python
def upgrade() -> None:
    op.create_table(
        "publication_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("draft_variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("draft_variants.id"), nullable=False),
        sa.Column("content_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_jobs.id"), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("workflow_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_versions.id"), nullable=False),
        sa.Column("trigger_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trigger_events.id"), nullable=True),
        sa.Column("platform", sa.Enum("x", "linkedin", "instagram", name="platform_enum", create_type=False), nullable=False),
        sa.Column("platform_post_id", sa.String(length=128), nullable=True),
        sa.Column("post_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publish_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
```

- [ ] **Step 2: Run targeted tests**

Run: `pytest tests/test_analytics_ingest.py tests/test_analytics_api.py tests/test_web_analytics_view.py tests/test_review_queue.py -q`
Expected: PASS

- [ ] **Step 3: Run the broader control-room suite**

Run: `pytest tests/test_control_room_api.py tests/test_trigger_api.py tests/test_linkedin_api.py tests/test_instagram_api.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/20260406_add_phase6_analytics_tables.py tests/conftest.py
git commit -m "feat: add phase 6 analytics persistence"
```

## Self-Review

- Spec coverage: this plan covers canonical publication records, analytics snapshots, workflow metrics, promotion confidence, API filters, and the analytics page. It intentionally does not include third-party analytics pullers yet; Phase 6 here is the control-room ingestion and reporting layer.
- Placeholder scan: no `TODO` or undefined implementation placeholders remain.
- Type consistency: plan uses existing canonical models (`Workflow`, `WorkflowVersion`, `ContentJob`, `DraftVariant`, `TriggerEvent`) and adds analytics on top without inventing a separate queue path.
