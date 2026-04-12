# Revenue Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the canonical revenue engine inside the control room so campaigns, leads, partner events, and manual operators can run revenue playbooks, generate `intent = revenue` drafts, produce sales enablement packages, and track conversion goals/events.

**Architecture:** Extend the existing trigger/workflow/draft pipeline rather than adding a separate sales subsystem. Revenue execution should be modeled with first-class records, feed the existing prompt assembler and workflow engine, and render through new API and control-room views that reuse the current campaign/lead/partner patterns.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Jinja2/HTMX, PostgreSQL enums/JSONB/UUID, pytest

---

## File Structure

- Create: `app/models/revenue.py`
  Defines `RevenuePlaybook`, `RevenueExecution`, `ConversionGoal`, `ConversionEvent`, and `SalesEnablementPackage`.
- Create: `app/services/revenue_service.py`
  Owns playbook bootstrap, execution, dashboard queries, sales-package creation, and conversion ingest.
- Create: `app/api/revenue_routes.py`
  Exposes revenue dashboard, playbook run, and conversion event endpoints.
- Create: `app/web/templates/revenue.html`
  Renders the control-room revenue screen.
- Create: `app/web/templates/partials/revenue_run_result.html`
  Renders HTMX results for manual playbook execution.
- Create: `alembic/versions/20260407_add_revenue_engine_tables.py`
  Adds canonical revenue tables.
- Modify: `app/models/__init__.py`
  Export new revenue models.
- Modify: `alembic/env.py`
  Import revenue models for metadata registration.
- Modify: `app/schemas/workflow_config.py`
  Add retrieval knobs for revenue context.
- Modify: `app/services/prompt_assembler.py`
  Extract and inject `revenue_context`.
- Modify: `app/services/workflow_engine.py`
  Persist revenue context into prompt snapshots.
- Modify: `app/main.py`
  Mount the new revenue API router.
- Modify: `app/web/routes.py`
  Add revenue dashboard loading and HTMX run endpoint.
- Modify: `app/web/templates/base.html`
  Add the revenue navigation entry.
- Modify: `app/services/partner_intake_service.py`
  Ensure partner-driven revenue playbooks can be resolved against partner events.
- Modify: `tests/test_alembic_revisions.py`
  Update the single-head assertion.
- Create: `tests/test_revenue_models.py`
- Create: `tests/test_revenue_service.py`
- Create: `tests/test_revenue_routes.py`
- Create: `tests/test_web_revenue_view.py`
- Modify: `tests/test_control_room_api.py`
  Assert revenue routes are mounted.
- Modify: `tests/test_partner_service.py`
  Cover partner-facing sales package behavior.
- Modify: `tests/test_campaign_service.py`
  Cover revenue-context propagation and playbook execution from campaigns.

---

### Task 1: Canonical Revenue Schema

**Files:**
- Create: `app/models/revenue.py`
- Modify: `app/models/__init__.py`
- Modify: `alembic/env.py`
- Create: `alembic/versions/20260407_add_revenue_engine_tables.py`
- Modify: `tests/test_alembic_revisions.py`
- Test: `tests/test_revenue_models.py`

- [ ] **Step 1: Write the failing model and migration tests**

```python
def test_revenue_playbook_and_conversion_models_round_trip():
    playbook = RevenuePlaybook(
        slug="alliance-registration-push",
        name="Alliance Registration Push",
        playbook_type="registration_push",
        persona="event_operator",
        offer="Register now",
        cta="Reserve your spot",
    )
    goal = ConversionGoal(
        slug="alliance-registration-completions",
        name="Alliance registration completions",
        metric_type="registrations",
        attribution_window_days=14,
    )
    event = ConversionEvent(
        conversion_goal_id=goal.id,
        external_event_id="conv-1",
        source_kind="partner_event",
        source_reference="evt-1",
        metric_value=1,
    )
    package = SalesEnablementPackage(
        revenue_playbook_id=playbook.id,
        package_kind="registration_push",
        status="needs_review",
        headline="Register now",
        body_copy="Proof-led copy",
        cta="Book now",
    )

    assert playbook.playbook_type == "registration_push"
    assert goal.metric_type == "registrations"
    assert event.metric_value == 1
    assert package.package_kind == "registration_push"


def test_alembic_has_single_head_revision():
    heads = script.get_heads()
    assert tuple(heads) == ("20260407_add_revenue_engine_tables",)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_revenue_models.py tests/test_alembic_revisions.py -q`
Expected: FAIL with missing `app.models.revenue` symbols and/or wrong Alembic head.

- [ ] **Step 3: Write the minimal schema and migration**

```python
class RevenuePlaybook(Base):
    __tablename__ = "revenue_playbooks"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = mapped_column(String(255), unique=True, nullable=False)
    playbook_type = mapped_column(String(64), nullable=False)
    workflow_id = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True)
    persona = mapped_column(String(128), nullable=False)
    offer = mapped_column(Text, nullable=False)
    cta = mapped_column(Text, nullable=False)
    metadata_json = mapped_column("metadata", JSONB, nullable=False, default=dict)


class RevenueExecution(Base):
    __tablename__ = "revenue_executions"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revenue_playbook_id = mapped_column(UUID(as_uuid=True), ForeignKey("revenue_playbooks.id"), nullable=False)
    source_kind = mapped_column(String(64), nullable=False)
    source_id = mapped_column(String(255), nullable=False)
    trigger_event_id = mapped_column(UUID(as_uuid=True), ForeignKey("trigger_events.id"), nullable=False)
    content_job_id = mapped_column(UUID(as_uuid=True), ForeignKey("content_jobs.id"), nullable=True)
    actor = mapped_column(String(128), nullable=False)
    status = mapped_column(String(32), nullable=False)
    summary = mapped_column(JSONB, nullable=False, default=dict)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_revenue_models.py tests/test_alembic_revisions.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/revenue.py app/models/__init__.py alembic/env.py \
  alembic/versions/20260407_add_revenue_engine_tables.py \
  tests/test_revenue_models.py tests/test_alembic_revisions.py
git commit -m "feat: add canonical revenue engine schema"
```

---

### Task 2: Revenue Context Plumbing

**Files:**
- Modify: `app/schemas/workflow_config.py`
- Modify: `app/services/prompt_assembler.py`
- Modify: `app/services/workflow_engine.py`
- Modify: `tests/test_campaign_service.py`
- Test: `tests/test_revenue_service.py`

- [ ] **Step 1: Write the failing context-propagation tests**

```python
def test_prompt_assembler_includes_revenue_context(monkeypatch):
    trigger = SimpleNamespace(source_payload={
        "request": "Drive registrations",
        "intent": "revenue",
        "revenue_context": {
            "playbook_slug": "alliance-registration-push",
            "persona": "event_operator",
            "offer": "Register now",
            "cta": "Reserve your spot",
        },
    })

    payload = PromptAssembler(fake_db).assemble(workflow, version, trigger)

    assert payload["revenue_context"]["playbook_slug"] == "alliance-registration-push"
    assert "Register now" in payload["user"]


def test_workflow_engine_prompt_snapshot_includes_revenue_context(monkeypatch):
    assert job.prompt_snapshot["revenue_context"]["cta"] == "Reserve your spot"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_campaign_service.py tests/test_revenue_service.py -q`
Expected: FAIL because `revenue_context` is not preserved by the assembler/engine.

- [ ] **Step 3: Implement minimal revenue-context support**

```python
class RetrievalConfig(BaseModel):
    include_revenue_context: bool = True
    revenue_context_fields: list[str] = Field(default_factory=list)


def _extract_revenue_context(...):
    base = payload.get("revenue_context") or {}
    if not include_revenue_context:
        return {}
    return {key: value for key, value in base.items() if value not in (None, "", [], {})}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_campaign_service.py tests/test_revenue_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/workflow_config.py app/services/prompt_assembler.py \
  app/services/workflow_engine.py tests/test_campaign_service.py tests/test_revenue_service.py
git commit -m "feat: add revenue context to workflow generation"
```

---

### Task 3: Revenue Service And Playbook Execution

**Files:**
- Create: `app/services/revenue_service.py`
- Modify: `app/services/partner_intake_service.py`
- Test: `tests/test_revenue_service.py`
- Modify: `tests/test_partner_service.py`

- [ ] **Step 1: Write the failing service tests**

```python
def test_run_playbook_by_slug_creates_manual_request_and_execution(monkeypatch):
    result = RevenueService(fake_db).run_playbook_by_slug(
        "alliance-registration-push",
        actor="sales",
        source_kind="partner_event",
        source_id="evt-1",
    )

    assert result["playbook_slug"] == "alliance-registration-push"
    assert result["intent"] == "revenue"
    assert result["status"] == "completed"


def test_partner_registration_playbook_creates_sales_enablement_package(monkeypatch):
    result = RevenueService(fake_db).run_playbook_by_slug(
        "alliance-registration-push",
        actor="ops",
        source_kind="partner_event",
        source_id="evt-1",
    )

    assert result["sales_package_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_revenue_service.py tests/test_partner_service.py -q`
Expected: FAIL with missing `RevenueService` and package-generation behavior.

- [ ] **Step 3: Implement the minimal service**

```python
class RevenueService:
    def run_playbook_by_slug(self, playbook_slug: str, *, actor: str, source_kind: str, source_id: str, context: dict | None = None) -> dict[str, Any]:
        playbook = self._get_playbook_by_slug(playbook_slug)
        trigger = self._build_trigger(playbook, source_kind=source_kind, source_id=source_id, actor=actor, context=context or {})
        job = self.workflow_engine.execute(trigger)
        execution = RevenueExecution(
            id=uuid.uuid4(),
            revenue_playbook_id=playbook.id,
            source_kind=source_kind,
            source_id=source_id,
            trigger_event_id=trigger.id,
            content_job_id=getattr(job, "id", None),
            actor=actor,
            status=job.status,
            summary={"intent": "revenue", "playbook_slug": playbook.slug},
        )
        self.db.add(execution)
        packages = self._create_sales_packages(playbook, source_kind=source_kind, source_id=source_id, content_job_id=getattr(job, "id", None))
        self.db.flush()
        return {"playbook_slug": playbook.slug, "intent": "revenue", "status": job.status, "sales_package_count": len(packages)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_revenue_service.py tests/test_partner_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/revenue_service.py app/services/partner_intake_service.py \
  tests/test_revenue_service.py tests/test_partner_service.py
git commit -m "feat: add revenue playbook execution service"
```

---

### Task 4: Revenue API

**Files:**
- Create: `app/api/revenue_routes.py`
- Modify: `app/main.py`
- Modify: `tests/test_control_room_api.py`
- Test: `tests/test_revenue_routes.py`

- [ ] **Step 1: Write the failing API tests**

```python
def test_revenue_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/control-room/revenue" in paths
    assert "/api/control-room/revenue/playbooks/{playbook_slug}/run" in paths
    assert "/api/control-room/revenue/conversions" in paths


def test_run_revenue_playbook_api_returns_summary(monkeypatch):
    response = client.post(
        "/api/control-room/revenue/playbooks/alliance-registration-push/run",
        headers={"Authorization": "Bearer test-secret-key"},
        json={"actor": "sales", "source_kind": "partner_event", "source_id": "evt-1"},
    )
    assert response.json()["playbook_slug"] == "alliance-registration-push"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_revenue_routes.py tests/test_control_room_api.py -q`
Expected: FAIL because the router is not mounted.

- [ ] **Step 3: Implement the router**

```python
router = APIRouter(
    prefix="/api/control-room/revenue",
    tags=["revenue"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("")
def revenue_dashboard(db: Session = Depends(get_db)):
    return RevenueService(db).list_dashboard()


@router.post("/playbooks/{playbook_slug}/run")
def run_playbook(...):
    result = RevenueService(db).run_playbook_by_slug(...)
    db.commit()
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_revenue_routes.py tests/test_control_room_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/revenue_routes.py app/main.py tests/test_revenue_routes.py tests/test_control_room_api.py
git commit -m "feat: add revenue engine api routes"
```

---

### Task 5: Revenue Control-Room UI

**Files:**
- Modify: `app/web/routes.py`
- Modify: `app/web/templates/base.html`
- Create: `app/web/templates/revenue.html`
- Create: `app/web/templates/partials/revenue_run_result.html`
- Test: `tests/test_web_revenue_view.py`

- [ ] **Step 1: Write the failing web-view tests**

```python
def test_revenue_view_renders_playbooks_and_conversion_goals(monkeypatch):
    response = client.get("/control-room/revenue")
    assert response.status_code == 200
    assert "Revenue" in response.text
    assert "Alliance Registration Push" in response.text


def test_revenue_run_fragment_renders_execution_result(monkeypatch):
    response = client.post(
        "/control-room/revenue/playbooks/alliance-registration-push/run",
        data={"actor": "sales", "source_kind": "partner_event", "source_id": "evt-1"},
    )
    assert "alliance-registration-push" in response.text
    assert "sales_package_count" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_web_revenue_view.py -q`
Expected: FAIL because the view and partial do not exist.

- [ ] **Step 3: Implement the minimal UI**

```python
@web_router.get("/revenue")
def revenue_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "revenue.html",
        {"page": "revenue", **RevenueService(db).list_dashboard()},
    )


@web_router.post("/revenue/playbooks/{playbook_slug}/run", response_class=HTMLResponse)
async def revenue_run_fragment(...):
    result = RevenueService(db).run_playbook_by_slug(...)
    db.commit()
    return templates.TemplateResponse(request, "partials/revenue_run_result.html", {"result": result})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_web_revenue_view.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/web/routes.py app/web/templates/base.html app/web/templates/revenue.html \
  app/web/templates/partials/revenue_run_result.html tests/test_web_revenue_view.py
git commit -m "feat: add revenue control room view"
```

---

### Task 6: Conversion Ingest And Full Regression

**Files:**
- Modify: `app/services/revenue_service.py`
- Modify: `app/api/revenue_routes.py`
- Modify: `tests/test_revenue_service.py`
- Modify: `tests/test_revenue_routes.py`
- Modify: `tests/test_campaign_service.py`
- Modify: `tests/test_partner_service.py`

- [ ] **Step 1: Write the failing conversion tests**

```python
def test_record_conversion_event_dedupes_on_goal_and_external_event_id():
    event = RevenueService(fake_db).record_conversion_event(
        goal_slug="alliance-registration-completions",
        external_event_id="conv-1",
        source_kind="partner_event",
        source_reference="evt-1",
        metric_value=1,
    )
    same = RevenueService(fake_db).record_conversion_event(
        goal_slug="alliance-registration-completions",
        external_event_id="conv-1",
        source_kind="partner_event",
        source_reference="evt-1",
        metric_value=1,
    )
    assert event["id"] == same["id"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_revenue_service.py tests/test_revenue_routes.py tests/test_campaign_service.py tests/test_partner_service.py -q`
Expected: FAIL because conversion ingest/dedupe is not implemented.

- [ ] **Step 3: Implement conversion recording and regression-safe wiring**

```python
def record_conversion_event(...):
    existing = self.db.query(ConversionEvent).filter(
        ConversionEvent.conversion_goal_id == goal.id,
        ConversionEvent.external_event_id == external_event_id,
    ).first()
    if existing:
        return self._serialize_conversion(existing)

    event = ConversionEvent(...)
    self.db.add(event)
    self.db.flush()
    return self._serialize_conversion(event)
```

- [ ] **Step 4: Run targeted regression and full suite**

Run: `pytest tests/test_revenue_models.py tests/test_revenue_service.py tests/test_revenue_routes.py tests/test_web_revenue_view.py tests/test_campaign_service.py tests/test_partner_service.py tests/test_control_room_api.py -q`
Expected: PASS

Run: `pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/revenue_service.py app/api/revenue_routes.py \
  tests/test_revenue_service.py tests/test_revenue_routes.py \
  tests/test_campaign_service.py tests/test_partner_service.py tests/test_control_room_api.py
git commit -m "feat: add revenue conversion tracking"
```

---

## Self-Review

- Spec coverage:
  - revenue intent: Tasks 2-3
  - playbook execution: Task 3
  - partner sales enablement: Tasks 3 and 6
  - conversion goals/events: Tasks 1 and 6
  - API/UI surfaces: Tasks 4 and 5
- Placeholder scan:
  - no `TODO`, `TBD`, or deferred implementation placeholders remain
- Type consistency:
  - `RevenuePlaybook`, `RevenueExecution`, `ConversionGoal`, `ConversionEvent`, and `SalesEnablementPackage` are defined in Task 1 and reused consistently later

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-07-revenue-engine.md`.

The user has already asked for implementation, so proceed with **Inline Execution** using `superpowers:executing-plans` on `partner-engine-all`.
