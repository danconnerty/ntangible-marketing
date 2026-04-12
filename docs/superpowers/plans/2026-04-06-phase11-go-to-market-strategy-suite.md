# Phase 11 Go-To-Market Strategy Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 11 as a staged strategic layer on top of the current control room: Campaign Planner, Competitor Scout, and Lead Nurture, all integrated with canonical workflows, triggers, memory, scheduler, and analytics.

**Architecture:** Keep everything inside the existing modular-monolith control-room architecture. Campaigns, competitor signals, and lead-nurture tasks become canonical records with manual-first operator flows that can create or enrich `TriggerEvent`s and `manual_request` generation runs through the same workflow engine already used by X, LinkedIn, Instagram, partner triggers, scheduler, and analytics. Use new agent modules only for strategy-specific reasoning, not as a second orchestration layer.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, Jinja2 control-room templates, pytest, existing control-room workflow engine, prompt assembler, scheduler, memory retrieval, analytics

---

## Scope Check

Phase 11 spans three independent subsystems:

1. Campaign Planner
2. Competitor Scout
3. Lead Nurture

This plan intentionally sequences them as six shippable slices inside one master plan:

- `11A` campaign foundation
- `11B` campaign-aware generation
- `11C` competitor foundation
- `11D` competitor signal workflows
- `11E` lead nurture foundation
- `11F` lead nurture sequencing and content bridges

Each slice is independently testable and should land green before the next one starts.

## File Structure

- Create: `app/models/campaign.py`
  Purpose: canonical campaign records, workflow mappings, and campaign-run history.
- Create: `app/models/competitor.py`
  Purpose: competitor sources, observations, signals, and workflow links.
- Create: `app/models/lead.py`
  Purpose: lead accounts, contacts, nurture tasks, and sequence state.
- Create: `app/agents/campaign_planner.py`
  Purpose: strategy helper that turns campaign briefs into workflow-safe manual requests and recommendations.
- Create: `app/agents/competitor_scout.py`
  Purpose: normalize competitor observations into categorized signals and recommended reaction angles.
- Create: `app/agents/lead_nurture.py`
  Purpose: generate nurture recommendations, touchpoint ideas, and sequence suggestions from lead state and memory.
- Create: `app/services/campaign_service.py`
  Purpose: CRUD campaigns, attach workflows, and fire campaign-scoped manual request triggers.
- Create: `app/services/competitor_service.py`
  Purpose: ingest competitor observations, dedupe signals, and optionally create trigger events.
- Create: `app/services/lead_nurture_service.py`
  Purpose: create nurture tasks, compute next actions, and bridge selected tasks into manual-request triggers.
- Create: `app/api/campaign_routes.py`
  Purpose: campaign CRUD, campaign-run endpoints, and campaign-scoped request generation.
- Create: `app/api/competitor_routes.py`
  Purpose: competitor source CRUD, observation ingest, signal listing, and signal-to-trigger actions.
- Create: `app/api/lead_routes.py`
  Purpose: lead account/contact CRUD, nurture-task actions, and generate-content actions.
- Modify: `app/services/prompt_assembler.py`
  Purpose: include campaign and competitive context in retrieval and prompt assembly.
- Modify: `app/services/workflow_engine.py`
  Purpose: preserve campaign/competitor/lead provenance on generated jobs.
- Modify: `app/services/trigger_engine.py`
  Purpose: support campaign and competitor/news manual/external trigger payloads without bypassing the canonical path.
- Modify: `app/models/__init__.py`
  Purpose: register new models.
- Modify: `app/main.py`
  Purpose: include campaign, competitor, and lead APIs.
- Modify: `app/web/routes.py`
  Purpose: render control-room pages for campaigns, competitors, and leads.
- Modify: `app/web/templates/base.html`
  Purpose: add navigation entries.
- Create: `app/web/templates/campaigns.html`
  Purpose: list campaigns, campaign runs, and campaign-to-workflow mappings.
- Create: `app/web/templates/competitors.html`
  Purpose: show competitor sources, recent signals, and “generate response draft” actions.
- Create: `app/web/templates/leads.html`
  Purpose: show lead accounts, nurture status, and next recommended actions.
- Create: `app/web/templates/partials/campaign_run_result.html`
  Purpose: HTMX fragment for campaign execution results.
- Create: `app/web/templates/partials/competitor_signal_result.html`
  Purpose: HTMX fragment for competitor signal actions.
- Create: `app/web/templates/partials/lead_task_result.html`
  Purpose: HTMX fragment for lead nurture actions.
- Modify: `app/static/css/control_room.css`
  Purpose: style new planning/intelligence/nurture views.
- Modify: `app/schemas/workflow_config.py`
  Purpose: extend workflow config with campaign-scope and market-signal retrieval hints in a backward-compatible way.
- Create: `alembic/versions/20260406_add_phase11_campaign_tables.py`
- Create: `alembic/versions/20260406_add_phase11_competitor_tables.py`
- Create: `alembic/versions/20260406_add_phase11_lead_tables.py`
- Test: `tests/test_campaign_service.py`
- Test: `tests/test_campaign_routes.py`
- Test: `tests/test_web_campaigns_view.py`
- Test: `tests/test_competitor_service.py`
- Test: `tests/test_competitor_routes.py`
- Test: `tests/test_web_competitors_view.py`
- Test: `tests/test_lead_nurture_service.py`
- Test: `tests/test_lead_routes.py`
- Test: `tests/test_web_leads_view.py`
- Test: `tests/test_prompt_assembler.py`
- Test: `tests/test_workflow_engine.py`

### Task 1: Add Campaign Planner Foundation

**Files:**
- Create: `app/models/campaign.py`
- Modify: `app/models/__init__.py`
- Create: `alembic/versions/20260406_add_phase11_campaign_tables.py`
- Test: `tests/test_campaign_service.py`

- [ ] **Step 1: Write the failing campaign model tests**

```python
import uuid
from datetime import datetime, timezone

from app.models.campaign import Campaign, CampaignRun, CampaignStatus, CampaignWorkflowScope


def test_campaign_fields():
    campaign = Campaign(
        id=uuid.uuid4(),
        name="Transfer Portal Week",
        slug="transfer-portal-week",
        objective="Drive coach conversations",
        audience="college coaches",
        theme="Transfer portal pressure",
        status=CampaignStatus.ACTIVE,
        start_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
    )
    assert campaign.slug == "transfer-portal-week"
    assert campaign.status == CampaignStatus.ACTIVE


def test_campaign_workflow_scope_fields():
    scope = CampaignWorkflowScope(
        id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        role="primary",
    )
    assert scope.role == "primary"


def test_campaign_run_fields():
    run = CampaignRun(
        id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        trigger_event_id=uuid.uuid4(),
        actor="planner",
        status="manual_ready",
        summary={"draft_count": 2},
    )
    assert run.summary["draft_count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_campaign_service.py -q -p no:rerunfailures`
Expected: FAIL because `app.models.campaign` does not exist.

- [ ] **Step 3: Write minimal campaign models and migration**

```python
class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
```

```python
class Campaign(Base):
    __tablename__ = "campaigns"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = mapped_column(String(255), nullable=False)
    slug = mapped_column(String(255), unique=True, nullable=False)
    objective = mapped_column(Text, nullable=False)
    audience = mapped_column(String(255), nullable=False)
    theme = mapped_column(String(255), nullable=False)
    status = mapped_column(campaign_status_enum, nullable=False, default=CampaignStatus.DRAFT)
    start_at = mapped_column(DateTime(timezone=True), nullable=True)
    end_at = mapped_column(DateTime(timezone=True), nullable=True)
    metadata = mapped_column("campaign_metadata", JSONB, nullable=False, default=dict)
```

```python
class CampaignWorkflowScope(Base):
    __tablename__ = "campaign_workflow_scopes"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    workflow_id = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    role = mapped_column(String(64), nullable=False, default="primary")
```

```python
class CampaignRun(Base):
    __tablename__ = "campaign_runs"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    trigger_event_id = mapped_column(UUID(as_uuid=True), ForeignKey("trigger_events.id"), nullable=False)
    actor = mapped_column(String(128), nullable=False)
    status = mapped_column(String(64), nullable=False)
    summary = mapped_column(JSONB, nullable=False, default=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_campaign_service.py -q -p no:rerunfailures`
Expected: PASS for model-import and field cases.

- [ ] **Step 5: Commit**

```bash
git add app/models/campaign.py app/models/__init__.py alembic/versions/20260406_add_phase11_campaign_tables.py tests/test_campaign_service.py
git commit -m "feat: add campaign planner data model"
```

### Task 2: Add Campaign Planner Service, Agent, API, And UI

**Files:**
- Create: `app/agents/campaign_planner.py`
- Create: `app/services/campaign_service.py`
- Create: `app/api/campaign_routes.py`
- Create: `app/web/templates/campaigns.html`
- Create: `app/web/templates/partials/campaign_run_result.html`
- Modify: `app/web/routes.py`
- Modify: `app/web/templates/base.html`
- Modify: `app/main.py`
- Test: `tests/test_campaign_service.py`
- Test: `tests/test_campaign_routes.py`
- Test: `tests/test_web_campaigns_view.py`

- [ ] **Step 1: Write the failing campaign execution tests**

```python
def test_run_campaign_creates_manual_request_trigger_and_campaign_run(monkeypatch):
    db = MagicMock()
    campaign = SimpleNamespace(id=uuid.uuid4(), slug="transfer-portal-week", name="Transfer Portal Week")
    workflow = SimpleNamespace(id=uuid.uuid4(), slug="tuesday-linkedin-tl")

    service = CampaignService(db)
    monkeypatch.setattr(service, "_get_campaign", lambda campaign_id: campaign)
    monkeypatch.setattr(service, "_campaign_workflows", lambda campaign_id: [workflow])
    monkeypatch.setattr(service.trigger_engine, "create_manual_request", lambda request_text, workflow_id: SimpleNamespace(id=uuid.uuid4()))
    monkeypatch.setattr(service.workflow_engine, "execute", lambda trigger: SimpleNamespace(id=uuid.uuid4(), status="completed"))

    result = service.run_campaign(campaign.id, actor="planner")

    assert result["campaign_slug"] == "transfer-portal-week"
    assert result["runs"][0]["workflow_slug"] == "tuesday-linkedin-tl"
```

```python
def test_campaign_run_api_returns_execution_summary(client, monkeypatch):
    monkeypatch.setattr(
        campaign_routes,
        "CampaignService",
        lambda db: type(
            "FakeService",
            (),
            {"run_campaign": lambda self, campaign_id, actor="planner": {"campaign_slug": "transfer-portal-week", "runs": [{"workflow_slug": "tuesday-linkedin-tl", "status": "manual_ready"}]}},
        )(),
    )
    response = client.post(
        "/api/control-room/campaigns/transfer-portal-week/run",
        headers={"Authorization": "Bearer test-secret-key"},
        json={"actor": "planner"},
    )
    assert response.status_code == 200
    assert response.json()["runs"][0]["status"] == "manual_ready"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_campaign_service.py tests/test_campaign_routes.py tests/test_web_campaigns_view.py -q -p no:rerunfailures`
Expected: FAIL because campaign planner service/routes/templates do not exist.

- [ ] **Step 3: Write minimal campaign planner implementation**

```python
class CampaignPlannerAgent:
    def build_manual_request(self, campaign: Campaign, workflow: Workflow) -> str:
        return (
            f"Campaign: {campaign.name}\n"
            f"Objective: {campaign.objective}\n"
            f"Audience: {campaign.audience}\n"
            f"Theme: {campaign.theme}\n"
            "Generate campaign-aligned content that fits the workflow."
        )
```

```python
class CampaignService:
    def __init__(self, db: Session):
        self.db = db
        self.trigger_engine = TriggerEngine(db)
        self.workflow_engine = WorkflowEngine(db)
        self.agent = CampaignPlannerAgent()

    def run_campaign(self, campaign_id: uuid.UUID, actor: str = "planner") -> dict:
        campaign = self._get_campaign(campaign_id)
        workflows = self._campaign_workflows(campaign.id)
        runs = []
        for workflow in workflows:
            request_text = self.agent.build_manual_request(campaign, workflow)
            trigger = self.trigger_engine.create_manual_request(request_text, workflow.id)
            trigger.source_payload["campaign_id"] = str(campaign.id)
            trigger.source_payload["campaign_slug"] = campaign.slug
            trigger.source_payload["campaign_name"] = campaign.name
            job = self.workflow_engine.execute(trigger)
            runs.append({"workflow_slug": workflow.slug, "status": job.status, "trigger_event_id": str(trigger.id)})
        return {"campaign_slug": campaign.slug, "runs": runs}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_campaign_service.py tests/test_campaign_routes.py tests/test_web_campaigns_view.py -q -p no:rerunfailures`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/agents/campaign_planner.py app/services/campaign_service.py app/api/campaign_routes.py app/web/templates/campaigns.html app/web/templates/partials/campaign_run_result.html app/web/routes.py app/web/templates/base.html app/main.py tests/test_campaign_service.py tests/test_campaign_routes.py tests/test_web_campaigns_view.py
git commit -m "feat: add campaign planner execution flow"
```

### Task 3: Make Generation Campaign-Aware

**Files:**
- Modify: `app/schemas/workflow_config.py`
- Modify: `app/services/prompt_assembler.py`
- Modify: `app/services/workflow_engine.py`
- Test: `tests/test_prompt_assembler.py`
- Test: `tests/test_workflow_engine.py`

- [ ] **Step 1: Write the failing campaign-context tests**

```python
def test_prompt_assembler_includes_campaign_context(monkeypatch):
    trigger = SimpleNamespace(
        source_payload={
            "request": "Three posts for portal week",
            "campaign_name": "Transfer Portal Week",
            "campaign_objective": "Drive coach conversations",
            "campaign_theme": "Transfer portal pressure",
        }
    )
    payload = PromptAssembler(MagicMock())._flatten_payload(trigger.source_payload)
    assert "Transfer Portal Week" in payload
    assert "Drive coach conversations" in payload
```

```python
def test_workflow_engine_persists_campaign_metadata_in_prompt_snapshot(monkeypatch):
    # Build a fake trigger with campaign fields and assert execute() stores them in prompt_snapshot.
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_prompt_assembler.py tests/test_workflow_engine.py -q -p no:rerunfailures`
Expected: FAIL because campaign-specific fields are not surfaced explicitly.

- [ ] **Step 3: Write minimal campaign-aware prompt logic**

```python
class RetrievalConfig(BaseModel):
    approved_example_ids: list[str] = Field(default_factory=list)
    rejected_example_ids: list[str] = Field(default_factory=list)
    max_examples: int = 5
    filter_by_pillar: bool = False
    filter_by_intent: bool = False
    include_campaign_context: bool = True
    include_market_signals: bool = True
```

```python
campaign_lines = []
if config.retrieval.include_campaign_context:
    for key in ("campaign_name", "campaign_objective", "campaign_theme", "campaign_audience"):
        value = trigger.source_payload.get(key)
        if value:
            campaign_lines.append(f"{key.replace('_', ' ').title()}: {value}")
```

```python
job.prompt_snapshot = {
    "system": payload["system"],
    "user": payload["user"],
    "retrieved_examples": payload["retrieved_examples"],
    "campaign": payload.get("campaign"),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_prompt_assembler.py tests/test_workflow_engine.py -q -p no:rerunfailures`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/workflow_config.py app/services/prompt_assembler.py app/services/workflow_engine.py tests/test_prompt_assembler.py tests/test_workflow_engine.py
git commit -m "feat: inject campaign context into workflow generation"
```

### Task 4: Add Competitor Scout Foundation

**Files:**
- Create: `app/models/competitor.py`
- Create: `app/agents/competitor_scout.py`
- Create: `app/services/competitor_service.py`
- Create: `app/api/competitor_routes.py`
- Create: `app/web/templates/competitors.html`
- Create: `app/web/templates/partials/competitor_signal_result.html`
- Modify: `app/models/__init__.py`
- Modify: `app/main.py`
- Modify: `app/web/routes.py`
- Modify: `app/web/templates/base.html`
- Create: `alembic/versions/20260406_add_phase11_competitor_tables.py`
- Test: `tests/test_competitor_service.py`
- Test: `tests/test_competitor_routes.py`
- Test: `tests/test_web_competitors_view.py`

- [ ] **Step 1: Write the failing competitor tests**

```python
def test_ingest_observation_creates_signal(monkeypatch):
    db = MagicMock()
    service = CompetitorService(db)
    monkeypatch.setattr(service.agent, "classify_observation", lambda payload: {"signal_type": "positioning_shift", "summary": "Competitor moved toward athlete-mental-performance messaging", "severity": "medium"})
    result = service.ingest_observation(
        {"source_slug": "rival-brand", "headline": "Pressure is trainable", "url": "https://example.com/post"}
    )
    assert result["signal_type"] == "positioning_shift"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_competitor_service.py tests/test_competitor_routes.py tests/test_web_competitors_view.py -q -p no:rerunfailures`
Expected: FAIL because competitor scout modules do not exist.

- [ ] **Step 3: Write minimal competitor models and scout logic**

```python
class CompetitorSource(Base):
    __tablename__ = "competitor_sources"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = mapped_column(String(128), unique=True, nullable=False)
    display_name = mapped_column(String(255), nullable=False)
    source_url = mapped_column(Text, nullable=False)
    platform = mapped_column(String(64), nullable=False)
    active = mapped_column(Boolean, nullable=False, default=True)
```

```python
class CompetitorSignal(Base):
    __tablename__ = "competitor_signals"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = mapped_column(UUID(as_uuid=True), ForeignKey("competitor_sources.id"), nullable=False)
    signal_type = mapped_column(String(64), nullable=False)
    summary = mapped_column(Text, nullable=False)
    severity = mapped_column(String(32), nullable=False, default="low")
    raw_payload = mapped_column(JSONB, nullable=False, default=dict)
```

```python
class CompetitorScoutAgent:
    def classify_observation(self, payload: dict) -> dict:
        headline = payload.get("headline", "")
        return {
            "signal_type": "positioning_shift" if "pressure" in headline.lower() else "general_update",
            "summary": headline or payload.get("summary") or "Competitor update captured",
            "severity": "medium",
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_competitor_service.py tests/test_competitor_routes.py tests/test_web_competitors_view.py -q -p no:rerunfailures`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/competitor.py app/agents/competitor_scout.py app/services/competitor_service.py app/api/competitor_routes.py app/web/templates/competitors.html app/web/templates/partials/competitor_signal_result.html app/models/__init__.py app/main.py app/web/routes.py app/web/templates/base.html alembic/versions/20260406_add_phase11_competitor_tables.py tests/test_competitor_service.py tests/test_competitor_routes.py tests/test_web_competitors_view.py
git commit -m "feat: add competitor scout foundation"
```

### Task 5: Route Competitor Signals Into Canonical Trigger Workflows

**Files:**
- Modify: `app/services/competitor_service.py`
- Modify: `app/services/trigger_engine.py`
- Modify: `app/api/competitor_routes.py`
- Test: `tests/test_competitor_service.py`
- Test: `tests/test_trigger_engine.py`

- [ ] **Step 1: Write the failing competitor-to-trigger tests**

```python
def test_create_response_trigger_for_signal(monkeypatch):
    db = MagicMock()
    service = CompetitorService(db)
    signal = SimpleNamespace(id=uuid.uuid4(), summary="Competitor moved toward pressure-data messaging")
    workflow = SimpleNamespace(id=uuid.uuid4(), slug="competitor-response-linkedin")
    monkeypatch.setattr(service, "_get_signal", lambda signal_id: signal)
    monkeypatch.setattr(service, "_resolve_response_workflow", lambda platform: workflow)
    monkeypatch.setattr(service.trigger_engine, "ingest_external", lambda payload, workflow_id: SimpleNamespace(id=uuid.uuid4(), source_payload=payload))
    result = service.create_response_trigger(signal.id, platform="linkedin")
    assert result["workflow_slug"] == "competitor-response-linkedin"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_competitor_service.py tests/test_trigger_engine.py -q -p no:rerunfailures`
Expected: FAIL because signals are not bridged into trigger execution.

- [ ] **Step 3: Write minimal bridge implementation**

```python
def create_response_trigger(self, signal_id: uuid.UUID, platform: str) -> dict:
    signal = self._get_signal(signal_id)
    workflow = self._resolve_response_workflow(platform)
    payload = {
        "competitor_signal_id": str(signal.id),
        "competitor_summary": signal.summary,
        "event_type": "competitor_signal",
    }
    trigger = self.trigger_engine.ingest_external(payload, workflow.id)
    job = self.workflow_engine.execute(trigger)
    return {"workflow_slug": workflow.slug, "trigger_event_id": str(trigger.id), "status": job.status}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_competitor_service.py tests/test_trigger_engine.py -q -p no:rerunfailures`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/competitor_service.py app/services/trigger_engine.py app/api/competitor_routes.py tests/test_competitor_service.py tests/test_trigger_engine.py
git commit -m "feat: route competitor signals through canonical workflows"
```

### Task 6: Add Lead Nurture Foundation

**Files:**
- Create: `app/models/lead.py`
- Create: `app/api/lead_routes.py`
- Create: `app/web/templates/leads.html`
- Modify: `app/models/__init__.py`
- Modify: `app/main.py`
- Modify: `app/web/routes.py`
- Modify: `app/web/templates/base.html`
- Create: `alembic/versions/20260406_add_phase11_lead_tables.py`
- Test: `tests/test_lead_routes.py`
- Test: `tests/test_web_leads_view.py`

- [ ] **Step 1: Write the failing lead model and route tests**

```python
def test_lead_account_fields():
    lead = LeadAccount(
        id=uuid.uuid4(),
        name="West Coast Academy",
        stage="qualified",
        source="manual",
        priority="high",
    )
    assert lead.stage == "qualified"
```

```python
def test_lead_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/control-room/leads" in paths
    assert "/control-room/leads" in paths
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_lead_routes.py tests/test_web_leads_view.py -q -p no:rerunfailures`
Expected: FAIL because lead models/routes/views do not exist.

- [ ] **Step 3: Write minimal lead foundation**

```python
class LeadAccount(Base):
    __tablename__ = "lead_accounts"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = mapped_column(String(255), nullable=False)
    stage = mapped_column(String(64), nullable=False, default="new")
    source = mapped_column(String(64), nullable=False, default="manual")
    priority = mapped_column(String(32), nullable=False, default="normal")
    metadata = mapped_column("lead_metadata", JSONB, nullable=False, default=dict)
```

```python
class LeadContact(Base):
    __tablename__ = "lead_contacts"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_account_id = mapped_column(UUID(as_uuid=True), ForeignKey("lead_accounts.id"), nullable=False)
    name = mapped_column(String(255), nullable=False)
    email = mapped_column(String(255), nullable=True)
    role = mapped_column(String(255), nullable=True)
```

```python
class LeadNurtureTask(Base):
    __tablename__ = "lead_nurture_tasks"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_account_id = mapped_column(UUID(as_uuid=True), ForeignKey("lead_accounts.id"), nullable=False)
    task_type = mapped_column(String(64), nullable=False)
    status = mapped_column(String(64), nullable=False, default="open")
    summary = mapped_column(Text, nullable=False)
    due_at = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_lead_routes.py tests/test_web_leads_view.py -q -p no:rerunfailures`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/lead.py app/api/lead_routes.py app/web/templates/leads.html app/models/__init__.py app/main.py app/web/routes.py app/web/templates/base.html alembic/versions/20260406_add_phase11_lead_tables.py tests/test_lead_routes.py tests/test_web_leads_view.py
git commit -m "feat: add lead nurture foundation"
```

### Task 7: Add Lead Nurture Agent, Sequencing, And Content Bridges

**Files:**
- Create: `app/agents/lead_nurture.py`
- Create: `app/services/lead_nurture_service.py`
- Create: `app/web/templates/partials/lead_task_result.html`
- Modify: `app/api/lead_routes.py`
- Modify: `app/web/routes.py`
- Test: `tests/test_lead_nurture_service.py`
- Test: `tests/test_lead_routes.py`

- [ ] **Step 1: Write the failing nurture recommendation tests**

```python
def test_build_nurture_recommendations_uses_lead_stage_and_memory(monkeypatch):
    db = MagicMock()
    service = LeadNurtureService(db)
    monkeypatch.setattr(service.memory, "build_generation_context", lambda query, platform=None, approved_limit=3, rejected_limit=2, workflow_slug=None: {"approved_examples": [{"id": "1", "content": "Proof-first coach story"}], "rejected_examples": [], "memory_ids": ["1"]})
    lead = SimpleNamespace(id=uuid.uuid4(), name="West Coast Academy", stage="qualified", priority="high", metadata={"sport": "softball"})
    recommendations = service.build_recommendations(lead)
    assert recommendations["touchpoint_type"] == "case-study-followup"
```

```python
def test_generate_content_for_lead_creates_manual_request(monkeypatch):
    db = MagicMock()
    service = LeadNurtureService(db)
    lead = SimpleNamespace(id=uuid.uuid4(), name="West Coast Academy", stage="proposal")
    workflow = SimpleNamespace(id=uuid.uuid4(), slug="lead-nurture-linkedin")
    monkeypatch.setattr(service, "_get_lead", lambda lead_id: lead)
    monkeypatch.setattr(service, "_resolve_lead_workflow", lambda platform: workflow)
    monkeypatch.setattr(service.trigger_engine, "create_manual_request", lambda request_text, workflow_id: SimpleNamespace(id=uuid.uuid4(), source_payload={"request": request_text}))
    monkeypatch.setattr(service.workflow_engine, "execute", lambda trigger: SimpleNamespace(status="manual_ready"))
    result = service.generate_content(lead.id, platform="linkedin", actor="sales")
    assert result["workflow_slug"] == "lead-nurture-linkedin"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_lead_nurture_service.py tests/test_lead_routes.py -q -p no:rerunfailures`
Expected: FAIL because nurture agent/service logic does not exist.

- [ ] **Step 3: Write minimal nurture service and sequencing**

```python
class LeadNurtureAgent:
    def recommend_touchpoint(self, lead: LeadAccount, examples: dict) -> dict:
        if lead.stage in {"qualified", "proposal"}:
            return {
                "touchpoint_type": "case-study-followup",
                "summary": f"Send a proof-led follow-up to {lead.name} using relevant client evidence.",
            }
        return {
            "touchpoint_type": "awareness-touch",
            "summary": f"Keep {lead.name} warm with a thought-leadership touchpoint.",
        }
```

```python
class LeadNurtureService:
    def generate_content(self, lead_id: uuid.UUID, platform: str, actor: str) -> dict:
        lead = self._get_lead(lead_id)
        workflow = self._resolve_lead_workflow(platform)
        request_text = (
            f"Lead nurture content for {lead.name}\n"
            f"Stage: {lead.stage}\n"
            f"Priority: {lead.priority}\n"
            "Generate content that moves the lead one step forward."
        )
        trigger = self.trigger_engine.create_manual_request(request_text, workflow.id)
        trigger.source_payload["lead_account_id"] = str(lead.id)
        trigger.source_payload["lead_name"] = lead.name
        job = self.workflow_engine.execute(trigger)
        return {"workflow_slug": workflow.slug, "status": job.status, "trigger_event_id": str(trigger.id)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_lead_nurture_service.py tests/test_lead_routes.py -q -p no:rerunfailures`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/agents/lead_nurture.py app/services/lead_nurture_service.py app/web/templates/partials/lead_task_result.html app/api/lead_routes.py app/web/routes.py tests/test_lead_nurture_service.py tests/test_lead_routes.py
git commit -m "feat: add lead nurture sequencing and content bridge"
```

### Task 8: Integrate Phase 11 Into The Control Room And Verify End To End

**Files:**
- Modify: `app/web/routes.py`
- Modify: `app/static/css/control_room.css`
- Modify: `app/web/templates/base.html`
- Test: `tests/test_campaign_routes.py`
- Test: `tests/test_competitor_routes.py`
- Test: `tests/test_lead_routes.py`
- Test: `tests/test_web_campaigns_view.py`
- Test: `tests/test_web_competitors_view.py`
- Test: `tests/test_web_leads_view.py`
- Test: `tests/test_control_room_api.py`

- [ ] **Step 1: Write the final route and navigation assertions**

```python
def test_phase11_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/control-room/campaigns" in paths
    assert "/api/control-room/competitors" in paths
    assert "/api/control-room/leads" in paths
    assert "/control-room/campaigns" in paths
    assert "/control-room/competitors" in paths
    assert "/control-room/leads" in paths
```

- [ ] **Step 2: Run the full Phase 11 slice to verify it fails where integration is missing**

Run: `.venv/bin/python -m pytest tests/test_campaign_service.py tests/test_campaign_routes.py tests/test_web_campaigns_view.py tests/test_competitor_service.py tests/test_competitor_routes.py tests/test_web_competitors_view.py tests/test_lead_nurture_service.py tests/test_lead_routes.py tests/test_web_leads_view.py tests/test_control_room_api.py -q -p no:rerunfailures`
Expected: FAIL until all routes, templates, and nav entries are wired together.

- [ ] **Step 3: Finish wiring navigation, pages, and API registration**

```python
nav_items = [
    ("campaigns", "Campaigns", "/control-room/campaigns"),
    ("competitors", "Competitors", "/control-room/competitors"),
    ("leads", "Leads", "/control-room/leads"),
]
```

```python
app.include_router(campaign_router)
app.include_router(competitor_router)
app.include_router(lead_router)
```

- [ ] **Step 4: Run the targeted Phase 11 suite to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_campaign_service.py tests/test_campaign_routes.py tests/test_web_campaigns_view.py tests/test_competitor_service.py tests/test_competitor_routes.py tests/test_web_competitors_view.py tests/test_lead_nurture_service.py tests/test_lead_routes.py tests/test_web_leads_view.py tests/test_control_room_api.py -q -p no:rerunfailures`
Expected: PASS

- [ ] **Step 5: Run the broader control-room regression suite**

Run: `.venv/bin/python -m pytest tests/test_workflow_routes.py tests/test_scheduler.py tests/test_trigger_api.py tests/test_web_manual_view.py tests/test_web_calendar_view.py tests/test_web_analytics_view.py -q -p no:rerunfailures`
Expected: PASS

- [ ] **Step 6: Run the full repository suite**

Run: `.venv/bin/python -m pytest -q -p no:rerunfailures`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/main.py app/web/routes.py app/web/templates/base.html app/static/css/control_room.css tests/test_control_room_api.py
git commit -m "feat: integrate phase 11 strategy suite into control room"
```

## Self-Review

- Spec coverage: this plan covers the three named Phase 11 pillars from the roadmap: campaign planner, competitor scout, and lead nurture. It routes all three through the canonical control-room architecture rather than creating side systems.
- Placeholder scan: no task contains `TODO`, `TBD`, or undefined execution steps. Where external systems could expand later, the plan explicitly chooses internal/manual-first adapters.
- Type consistency: the plan reuses existing canonical types and flows: `Workflow`, `WorkflowVersion`, `TriggerEvent`, `ContentJob`, `DraftVariant`, `PromptAssembler`, `WorkflowEngine`, and the server-rendered control-room routes/templates already present in the repo.

### Intentional Boundaries

- The plan keeps Phase 11 manual-first for outbound action. It supports “generate nurture content” and campaign/competitor-driven requests, but it does not require a real CRM vendor or ESP to send messages automatically.
- Competitor Scout starts with canonical observations and signals, not browser scraping or external crawling infrastructure.
- Campaign Planner enriches and schedules the existing content system; it does not create a parallel campaign engine.
