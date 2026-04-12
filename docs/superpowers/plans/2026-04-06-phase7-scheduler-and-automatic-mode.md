# Phase 7: Scheduler And Automatic Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the canonical scheduler worker, workflow-level automatic controls, and workflow-first Automatic UI for X, LinkedIn, and Instagram.

**Architecture:** Extend the canonical control-room model instead of reviving legacy platform queues. The worker remains a one-shot tick service that claims due rules and due drafts, while workflow-level controls and UI read/write scheduler state through shared workflow and review models.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, Jinja2/HTMX templates, pytest

---

## File Map

- Modify: `app/models/workflow.py`
- Modify: `app/models/trigger.py`
- Modify: `app/models/review.py`
- Modify: `app/services/trigger_generation.py`
- Modify: `app/services/review_queue.py`
- Modify: `app/services/scheduler.py`
- Modify: `app/api/control_room_routes.py`
- Modify: `app/web/routes.py`
- Modify: `app/web/templates/automatic.html`
- Modify: `app/web/templates/home.html`
- Create: `scripts/run_scheduler_tick.py`
- Create: `alembic/versions/20260406_phase7_scheduler_automatic_mode.py`
- Modify: `tests/test_scheduler.py`
- Modify: `tests/test_control_room_api.py`
- Modify: `tests/test_web_routes.py`

### Task 1: Add Scheduler State Fields And Workflow Controls

**Files:**
- Modify: `app/models/workflow.py`
- Modify: `app/models/trigger.py`
- Modify: `app/models/review.py`
- Create: `alembic/versions/20260406_phase7_scheduler_automatic_mode.py`
- Modify: `tests/test_control_room_api.py`

- [ ] **Step 1: Write the failing API/model tests for workflow-level automatic controls**

```python
def test_move_to_manual_requeues_pending_automatic_drafts(client, db_session, api_key_headers):
    workflow = Workflow(
        name="Automatic X Workflow",
        slug="automatic-x-workflow",
        platform=Platform.X,
        content_type="stat_update",
        mode=WorkflowMode.AUTOMATIC,
        timezone="America/Toronto",
        health_status="healthy",
    )
    db_session.add(workflow)
    db_session.flush()

    version = WorkflowVersion(
        workflow_id=workflow.id,
        version_number=1,
        config={"pillar": "events"},
        author="tester",
        is_active=True,
    )
    workflow.active_version_id = version.id
    db_session.add(version)
    db_session.flush()

    trigger = TriggerEvent(
        trigger_type=TriggerType.CALENDAR,
        workflow_id=workflow.id,
        source_payload={"cron_expression": "0 9 * * *"},
    )
    db_session.add(trigger)
    db_session.flush()

    job = ContentJob(
        workflow_id=workflow.id,
        workflow_version_id=version.id,
        trigger_event_id=trigger.id,
        prompt_snapshot={},
        compliance_snapshot={},
        status="completed",
    )
    db_session.add(job)
    db_session.flush()

    automatic_draft = DraftVariant(
        content_job_id=job.id,
        platform=Platform.X,
        content="Queued automatic draft",
        state=DraftState.AUTOMATIC_READY,
        timezone="America/Toronto",
    )
    db_session.add(automatic_draft)
    db_session.commit()

    response = client.post(
        f"/api/control-room/workflows/{workflow.id}/move-to-manual",
        headers=api_key_headers,
    )

    assert response.status_code == 200
    db_session.refresh(workflow)
    db_session.refresh(automatic_draft)
    assert workflow.mode == WorkflowMode.MANUAL
    assert automatic_draft.state == DraftState.MANUAL_READY


def test_pause_workflow_sets_paused_at_and_scheduler_health(client, db_session, api_key_headers):
    workflow = Workflow(
        name="Automatic LinkedIn Workflow",
        slug="automatic-linkedin-workflow",
        platform=Platform.LINKEDIN,
        content_type="thought_leadership",
        mode=WorkflowMode.AUTOMATIC,
        timezone="America/Toronto",
        health_status="healthy",
    )
    db_session.add(workflow)
    db_session.commit()

    response = client.post(
        f"/api/control-room/workflows/{workflow.id}/pause",
        headers=api_key_headers,
    )

    assert response.status_code == 200
    db_session.refresh(workflow)
    assert workflow.paused_at is not None
    assert workflow.health_status == "paused"
```

- [ ] **Step 2: Run the focused API tests to verify they fail**

Run: `pytest tests/test_control_room_api.py -k "move_to_manual_requeues_pending_automatic_drafts or pause_workflow_sets_paused_at_and_scheduler_health" -v`

Expected: FAIL with missing workflow fields and missing workflow control routes.

- [ ] **Step 3: Add the scheduler/workflow fields and migration**

```python
class Workflow(Base):
    ...
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/New_York")
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_status: Mapped[str] = mapped_column(String(32), nullable=False, default="healthy")


class CalendarRule(Base):
    ...
    publish_hour_local: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publish_minute_local: Mapped[int | None] = mapped_column(Integer, nullable=True)
    all_day_generation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)


class DraftVariant(Base):
    ...
    publish_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_via: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

```python
def upgrade() -> None:
    op.add_column("workflows", sa.Column("timezone", sa.String(length=64), nullable=False, server_default="America/New_York"))
    op.add_column("workflows", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflows", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflows", sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflows", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("workflows", sa.Column("health_status", sa.String(length=32), nullable=False, server_default="healthy"))
    op.add_column("calendar_rules", sa.Column("publish_hour_local", sa.Integer(), nullable=True))
    op.add_column("calendar_rules", sa.Column("publish_minute_local", sa.Integer(), nullable=True))
    op.add_column("calendar_rules", sa.Column("all_day_generation", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("calendar_rules", sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("calendar_rules", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("calendar_rules", sa.Column("claimed_by", sa.String(length=128), nullable=True))
    op.add_column("draft_variants", sa.Column("publish_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("draft_variants", sa.Column("published_via", sa.String(length=32), nullable=True))
```

- [ ] **Step 4: Add workflow-level control helpers and API routes**

```python
def _load_workflow_or_404(db: Session, workflow_id: str) -> Workflow:
    workflow = db.query(Workflow).filter(Workflow.id == uuid.UUID(workflow_id)).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


def _set_workflow_pause_state(db: Session, workflow: Workflow, paused: bool) -> Workflow:
    workflow.paused_at = datetime.now(timezone.utc) if paused else None
    workflow.health_status = "paused" if paused else "healthy"
    workflow.last_error = None if not paused else workflow.last_error
    db.flush()
    return workflow


@router.post("/workflows/{workflow_id}/pause")
def pause_workflow(workflow_id: str, db: Session = Depends(get_db)):
    workflow = _load_workflow_or_404(db, workflow_id)
    _set_workflow_pause_state(db, workflow, paused=True)
    db.commit()
    return {"workflow_id": str(workflow.id), "status": "paused"}


@router.post("/workflows/{workflow_id}/move-to-manual")
def move_workflow_to_manual(workflow_id: str, db: Session = Depends(get_db)):
    workflow = _load_workflow_or_404(db, workflow_id)
    workflow.mode = WorkflowMode.MANUAL
    workflow.paused_at = None
    workflow.health_status = "healthy"
    (
        db.query(DraftVariant)
        .join(ContentJob, ContentJob.id == DraftVariant.content_job_id)
        .filter(
            ContentJob.workflow_id == workflow.id,
            DraftVariant.state == DraftState.AUTOMATIC_READY,
        )
        .update(
            {
                DraftVariant.state: DraftState.MANUAL_READY,
                DraftVariant.scheduled_publish_at: None,
                DraftVariant.published_via: None,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {"workflow_id": str(workflow.id), "status": "manual"}
```

- [ ] **Step 5: Run the focused API tests to verify they pass**

Run: `pytest tests/test_control_room_api.py -k "move_to_manual_requeues_pending_automatic_drafts or pause_workflow_sets_paused_at_and_scheduler_health" -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/models/workflow.py app/models/trigger.py app/models/review.py app/api/control_room_routes.py alembic/versions/20260406_phase7_scheduler_automatic_mode.py tests/test_control_room_api.py
git commit -m "feat: add workflow scheduler state and controls"
```

### Task 2: Make The Scheduler Canonical, Claim-Safe, And Cross-Platform

**Files:**
- Modify: `app/services/scheduler.py`
- Modify: `app/services/trigger_generation.py`
- Modify: `app/services/review_queue.py`
- Create: `scripts/run_scheduler_tick.py`
- Modify: `tests/test_scheduler.py`

- [ ] **Step 1: Write the failing scheduler tests**

```python
def test_scheduler_skips_paused_workflow_rules(db_session):
    workflow = Workflow(
        name="Paused Workflow",
        slug="paused-workflow",
        platform=Platform.X,
        content_type="stat_update",
        mode=WorkflowMode.AUTOMATIC,
        paused_at=datetime.now(timezone.utc),
        timezone="America/Toronto",
    )
    db_session.add(workflow)
    db_session.flush()

    rule = CalendarRule(
        workflow_id=workflow.id,
        cron_expression="0 9 * * *",
        timezone="America/Toronto",
        enabled=True,
        next_fire_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(rule)
    db_session.commit()

    fired = SchedulerService(db_session).fire_due_calendar_rules(datetime.now(timezone.utc))

    assert fired == 0


def test_scheduler_records_publish_metadata_for_instagram_due_draft(db_session):
    draft = DraftVariant(
        content_job_id=uuid.uuid4(),
        platform=Platform.INSTAGRAM,
        content="Caption",
        hashtags=["#team"],
        state=DraftState.AUTOMATIC_READY,
        timezone="America/Toronto",
        scheduled_publish_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        compliance_result={"publish_mode": "feed"},
    )
    db_session.add(draft)
    db_session.flush()
    db_session.add(
        Asset(
            draft_variant_id=draft.id,
            asset_type="image",
            asset_role="primary",
            url="https://example.com/image.png",
            sort_order=0,
        )
    )
    db_session.commit()

    with patch("app.services.review_queue.get_instagram_publisher") as publisher_factory:
        publisher_factory.return_value.publish_post.return_value = InstagramPublishResult(
            success=True,
            post_id="ig-123",
            post_url="https://instagram.com/p/ig-123",
        )
        published = SchedulerService(db_session).publish_due_drafts(datetime.now(timezone.utc))

    db_session.refresh(draft)
    assert published == 1
    assert draft.state == DraftState.PUBLISHED
    assert draft.published_via == "automatic_workflow"
    assert draft.publish_attempted_at is not None
```

- [ ] **Step 2: Run the focused scheduler tests to verify they fail**

Run: `pytest tests/test_scheduler.py -k "paused_workflow_rules or publish_metadata_for_instagram_due_draft" -v`

Expected: FAIL because paused workflows are not filtered and publication metadata is not recorded.

- [ ] **Step 3: Add Instagram generation support and scheduler tick/result behavior**

```python
def generate_trigger_draft(request) -> GeneratedTriggerDraft:
    if request.platform == Platform.X:
        return _generate_x_draft(request)
    if request.platform == Platform.LINKEDIN:
        return _generate_linkedin_draft(request)
    if request.platform == Platform.INSTAGRAM:
        return _generate_instagram_draft(request)
    raise ValueError(f"Unsupported trigger platform: {request.platform.value}")
```

```python
@dataclass(frozen=True)
class SchedulerTickResult:
    calendar_rules_fired: int = 0
    drafts_published: int = 0
    manual_drafts_expired: int = 0
    workflow_failures: int = 0


def tick(self, now: datetime | None = None) -> SchedulerTickResult:
    now = now or datetime.now(timezone.utc)
    fired, failures = self.fire_due_calendar_rules(now)
    expired = self.expire_due_manual_drafts(now)
    published, publish_failures = self.publish_due_drafts(now)
    return SchedulerTickResult(
        calendar_rules_fired=fired,
        drafts_published=published,
        manual_drafts_expired=expired,
        workflow_failures=failures + publish_failures,
    )
```

- [ ] **Step 4: Make the scheduler claim-safe and update workflow health**

```python
def _due_rules(self, now: datetime) -> list[CalendarRule]:
    return (
        self.db.query(CalendarRule)
        .join(Workflow, Workflow.id == CalendarRule.workflow_id)
        .filter(
            CalendarRule.enabled.is_(True),
            CalendarRule.next_fire_at.isnot(None),
            CalendarRule.next_fire_at <= now,
            Workflow.enabled.is_(True),
            Workflow.paused_at.is_(None),
        )
        .order_by(CalendarRule.next_fire_at.asc())
        .limit(self.batch_limit)
        .all()
    )


def _claim_rule(self, rule: CalendarRule, now: datetime) -> bool:
    updated = (
        self.db.query(CalendarRule)
        .filter(
            CalendarRule.id == rule.id,
            CalendarRule.claimed_at.is_(None),
        )
        .update(
            {
                CalendarRule.claimed_at: now,
                CalendarRule.claimed_by: self.worker_name,
            },
            synchronize_session=False,
        )
    )
    self.db.flush()
    return updated == 1
```

```python
def _publish_draft(self, draft: DraftVariant, *, published_via: str) -> None:
    draft.publish_attempted_at = datetime.now(timezone.utc)
    draft.published_via = published_via
    ...
```

- [ ] **Step 5: Add the one-shot worker entrypoint**

```python
from app.database import SessionLocal
from app.services.scheduler import SchedulerService


def main() -> None:
    db = SessionLocal()
    try:
        result = SchedulerService(db).tick()
        db.commit()
        print(result)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run focused scheduler tests and the whole scheduler file**

Run: `pytest tests/test_scheduler.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/scheduler.py app/services/trigger_generation.py app/services/review_queue.py scripts/run_scheduler_tick.py tests/test_scheduler.py
git commit -m "feat: add canonical scheduler worker"
```

### Task 3: Add Workflow-First Automatic APIs And Status Visibility

**Files:**
- Modify: `app/api/control_room_routes.py`
- Modify: `tests/test_control_room_api.py`

- [ ] **Step 1: Write the failing API tests for automatic workflow listing and scheduler status**

```python
def test_list_automatic_workflows_groups_queued_drafts_by_workflow(client, db_session, api_key_headers):
    workflow = Workflow(
        name="Instagram Auto Workflow",
        slug="instagram-auto-workflow",
        platform=Platform.INSTAGRAM,
        content_type="carousel",
        mode=WorkflowMode.AUTOMATIC,
        timezone="America/Toronto",
        health_status="healthy",
    )
    db_session.add(workflow)
    db_session.commit()

    response = client.get("/api/control-room/automatic/workflows", headers=api_key_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["workflows"][0]["workflow_name"] == "Instagram Auto Workflow"


def test_scheduler_status_reports_paused_and_upcoming_counts(client, db_session, api_key_headers):
    response = client.get("/api/control-room/scheduler/status", headers=api_key_headers)

    assert response.status_code == 200
    payload = response.json()
    assert "paused_workflows" in payload
    assert "upcoming_24h" in payload
```

- [ ] **Step 2: Run the focused API tests to verify they fail**

Run: `pytest tests/test_control_room_api.py -k "list_automatic_workflows_groups_queued_drafts_by_workflow or scheduler_status_reports_paused_and_upcoming_counts" -v`

Expected: FAIL with missing routes/serializer output.

- [ ] **Step 3: Add workflow-first automatic serializers and routes**

```python
def _serialize_automatic_workflow(db: Session, workflow: Workflow) -> dict:
    queued_drafts = (
        db.query(DraftVariant)
        .join(ContentJob, ContentJob.id == DraftVariant.content_job_id)
        .filter(
            ContentJob.workflow_id == workflow.id,
            DraftVariant.state.in_([DraftState.AUTOMATIC_READY, DraftState.SCHEDULED_MANUAL]),
        )
        .order_by(DraftVariant.scheduled_publish_at.asc(), DraftVariant.created_at.asc())
        .all()
    )
    next_rule = (
        db.query(CalendarRule)
        .filter(CalendarRule.workflow_id == workflow.id, CalendarRule.enabled.is_(True))
        .order_by(CalendarRule.next_fire_at.asc())
        .first()
    )
    return {
        "workflow_id": str(workflow.id),
        "workflow_name": workflow.name,
        "workflow_slug": workflow.slug,
        "platform": workflow.platform.value,
        "mode": workflow.mode.value,
        "timezone": workflow.timezone,
        "health_status": workflow.health_status,
        "paused_at": workflow.paused_at.isoformat() if workflow.paused_at else None,
        "next_trigger_at": next_rule.next_fire_at.isoformat() if next_rule and next_rule.next_fire_at else None,
        "queued_draft_count": len(queued_drafts),
        "drafts": [_serialize_draft(draft) for draft in queued_drafts],
    }
```

```python
@router.get("/automatic/workflows")
def list_automatic_workflows(db: Session = Depends(get_db)):
    workflows = (
        db.query(Workflow)
        .filter(Workflow.mode == WorkflowMode.AUTOMATIC, Workflow.enabled.is_(True))
        .order_by(Workflow.name.asc())
        .all()
    )
    payload = [_serialize_automatic_workflow(db, workflow) for workflow in workflows]
    return {"workflows": payload, "count": len(payload)}


@router.get("/scheduler/status")
def scheduler_status(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    upcoming_24h = (
        db.query(DraftVariant)
        .filter(
            DraftVariant.state.in_([DraftState.AUTOMATIC_READY, DraftState.SCHEDULED_MANUAL]),
            DraftVariant.scheduled_publish_at.isnot(None),
            DraftVariant.scheduled_publish_at <= now + timedelta(hours=24),
        )
        .count()
    )
    return {
        "paused_workflows": db.query(Workflow).filter(Workflow.paused_at.isnot(None)).count(),
        "unhealthy_workflows": db.query(Workflow).filter(Workflow.health_status == "unhealthy").count(),
        "upcoming_24h": upcoming_24h,
    }
```

- [ ] **Step 4: Run the focused API tests to verify they pass**

Run: `pytest tests/test_control_room_api.py -k "list_automatic_workflows_groups_queued_drafts_by_workflow or scheduler_status_reports_paused_and_upcoming_counts" -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/control_room_routes.py tests/test_control_room_api.py
git commit -m "feat: add workflow-first automatic control room api"
```

### Task 4: Replace The Draft-First Automatic UI With Workflow-First Views

**Files:**
- Modify: `app/web/routes.py`
- Modify: `app/web/templates/automatic.html`
- Modify: `app/web/templates/home.html`
- Modify: `tests/test_web_routes.py`

- [ ] **Step 1: Write the failing web tests**

```python
def test_automatic_view_renders_workflow_cards(client, db_session):
    workflow = Workflow(
        name="Auto Instagram",
        slug="auto-instagram",
        platform=Platform.INSTAGRAM,
        content_type="carousel",
        mode=WorkflowMode.AUTOMATIC,
        timezone="America/Toronto",
        health_status="healthy",
    )
    db_session.add(workflow)
    db_session.commit()

    response = client.get("/control-room/automatic")

    assert response.status_code == 200
    assert "Auto Instagram" in response.text
    assert "Next Trigger" in response.text
    assert "Queued Drafts" in response.text


def test_home_view_shows_paused_and_upcoming_automatic_counts(client, db_session):
    response = client.get("/control-room/")

    assert response.status_code == 200
    assert "Paused Workflows" in response.text
    assert "Upcoming Auto (24h)" in response.text
```

- [ ] **Step 2: Run the focused web tests to verify they fail**

Run: `pytest tests/test_web_routes.py -k "automatic_view_renders_workflow_cards or home_view_shows_paused_and_upcoming_automatic_counts" -v`

Expected: FAIL because the automatic template is draft-first and the home template omits scheduler counts.

- [ ] **Step 3: Add workflow-first loaders and web actions**

```python
def load_automatic_workflow_cards(db: Session) -> list[dict[str, Any]]:
    workflows = (
        db.query(Workflow)
        .filter(Workflow.mode == WorkflowMode.AUTOMATIC, Workflow.enabled.is_(True))
        .order_by(Workflow.name.asc())
        .all()
    )
    return [_serialize_automatic_workflow_summary(db, workflow) for workflow in workflows]
```

```python
@web_router.get("/automatic")
def automatic_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "automatic.html",
        {
            "page": "automatic",
            "workflows": load_automatic_workflow_cards(db),
        },
    )
```

- [ ] **Step 4: Replace the template and home stats**

```html
{% if workflows %}
<div class="workflow-grid">
  {% for workflow in workflows %}
  <article class="workflow-card">
    <header>
      <h2>{{ workflow.workflow_name }}</h2>
      <span class="badge">{{ workflow.health_status }}</span>
    </header>
    <p>{{ workflow.platform }} · {{ workflow.timezone }}</p>
    <dl>
      <div><dt>Next Trigger</dt><dd>{{ workflow.next_trigger_label or '—' }}</dd></div>
      <div><dt>Publish Time</dt><dd>{{ workflow.publish_time_label or '—' }}</dd></div>
      <div><dt>Queued Drafts</dt><dd>{{ workflow.queued_draft_count }}</dd></div>
      <div><dt>Last Success</dt><dd>{{ workflow.last_success_label or '—' }}</dd></div>
    </dl>
  </article>
  {% endfor %}
</div>
{% endif %}
```

- [ ] **Step 5: Run the focused web tests to verify they pass**

Run: `pytest tests/test_web_routes.py -k "automatic_view_renders_workflow_cards or home_view_shows_paused_and_upcoming_automatic_counts" -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/web/routes.py app/web/templates/automatic.html app/web/templates/home.html tests/test_web_routes.py
git commit -m "feat: add workflow-first automatic ui"
```

### Task 5: Run Full Verification For Phase 7

**Files:**
- Modify: `tests/test_scheduler.py`
- Modify: `tests/test_control_room_api.py`
- Modify: `tests/test_web_routes.py`

- [ ] **Step 1: Run the targeted Phase 7 suite**

Run: `pytest tests/test_scheduler.py tests/test_control_room_api.py tests/test_web_routes.py -v`

Expected: PASS

- [ ] **Step 2: Run the full repository suite**

Run: `pytest tests/ -v`

Expected: PASS

- [ ] **Step 3: Review the Phase 7 spec against the implementation**

Checklist:
- Manual workflows still create `manual_ready` drafts and expire at local end-of-day.
- Automatic workflows create `automatic_ready` drafts with exact `scheduled_publish_at`.
- Due automatic and scheduled-manual drafts publish via canonical adapters.
- Paused workflows do not generate or auto-publish.
- Move-to-manual requeues pending automatic drafts.
- Automatic UI is workflow-first and shows health plus queued drafts.
- Calendar/home/status views reflect authoritative automatic timing.

- [ ] **Step 4: Commit**

```bash
git add tests/test_scheduler.py tests/test_control_room_api.py tests/test_web_routes.py
git commit -m "test: verify phase 7 scheduler and automatic mode"
```
