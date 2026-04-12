# Partner Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full Alliance + FSS partner engine with webhook intake, partner portal, partner hub, partner routing, partner delivery bundles, and partner intent persistence.

**Architecture:** Add canonical partner records and services on top of the existing control-room pipeline. Reuse the trigger/workflow/review stack for generation, and add a partner portal plus control-room hub as thin surfaces over the same backend services.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja2, HTMX, Postgres/Alembic, pytest

---

## File Structure

- Create: `app/models/partner.py`
  Purpose: canonical partner accounts, event records, and delivery bundles.
- Create: `app/services/partner_intake_service.py`
  Purpose: webhook/portal ingestion, normalization, and event-record creation.
- Create: `app/services/partner_delivery_service.py`
  Purpose: convert partner-triggered drafts into delivery bundles.
- Create: `app/api/partner_routes.py`
  Purpose: partner account listing, intake endpoints, bundle actions, and hub APIs.
- Create: `app/web/partner_portal.py`
  Purpose: partner-facing portal routes and auth.
- Create: `app/web/templates/partners.html`
  Purpose: control-room partner hub.
- Create: `app/web/templates/partner_portal_login.html`
  Purpose: partner portal login screen.
- Create: `app/web/templates/partner_portal_submit.html`
  Purpose: partner portal submission UI.
- Create: `app/web/templates/partner_portal_packages.html`
  Purpose: partner-facing bundle view.
- Create: `app/web/templates/partials/partner_event_result.html`
  Purpose: HTMX fragment for intake results.
- Create: `app/web/templates/partials/partner_bundle_result.html`
  Purpose: HTMX fragment for bundle actions.
- Modify: `app/triggers/partner_events.py`
  Purpose: add missing partner event types and routing rules.
- Modify: `app/models/review.py`
  Purpose: persist content intent on canonical drafts.
- Modify: `app/services/workflow_engine.py`
  Purpose: write partner intent/provenance to jobs and drafts.
- Modify: `app/services/prompt_assembler.py`
  Purpose: include richer partner context in prompt assembly.
- Modify: `app/web/routes.py`
  Purpose: add partner hub views.
- Modify: `app/web/templates/base.html`
  Purpose: add partner hub navigation.
- Modify: `app/main.py`
  Purpose: register partner API and partner portal routes.
- Modify: `app/models/__init__.py`
  Purpose: register partner models.
- Create: `alembic/versions/20260407_add_partner_engine_tables.py`
- Test: `tests/test_partner_models.py`
- Test: `tests/test_partner_service.py`
- Test: `tests/test_partner_routes.py`
- Test: `tests/test_partner_portal_view.py`
- Test: `tests/test_web_partners_view.py`
- Test: `tests/test_partner_routing.py`

---

### Task 1: Add Canonical Partner Models

**Files:**
- Create: `app/models/partner.py`
- Modify: `app/models/__init__.py`
- Create: `alembic/versions/20260407_add_partner_engine_tables.py`
- Test: `tests/test_partner_models.py`

- [ ] **Step 1: Write the failing test**

```python
import uuid

from app.models.partner import PartnerAccount, PartnerDeliveryBundle, PartnerEventRecord


def test_partner_account_fields():
    partner = PartnerAccount(
        id=uuid.uuid4(),
        slug="alliance-fastpitch",
        display_name="Alliance Fastpitch",
        portal_username="alliance",
        portal_password_hash="hash",
        webhook_secret="secret",
        supported_event_types=["assessment_completed", "leaderboard_published"],
    )
    assert partner.slug == "alliance-fastpitch"


def test_partner_event_record_fields():
    event = PartnerEventRecord(
        id=uuid.uuid4(),
        partner_account_id=uuid.uuid4(),
        intake_source="webhook",
        event_type="assessment_completed",
        external_event_id="evt-123",
        raw_payload={},
        normalized_payload={},
        processing_status="received",
    )
    assert event.event_type == "assessment_completed"


def test_partner_delivery_bundle_fields():
    bundle = PartnerDeliveryBundle(
        id=uuid.uuid4(),
        partner_account_id=uuid.uuid4(),
        partner_event_record_id=uuid.uuid4(),
        draft_variant_id=uuid.uuid4(),
        platform="instagram",
        status="needs_review",
        caption="Partner-ready caption",
        hashtags=["#AllianceFastpitch"],
        asset_ids=[],
        delivery_payload={},
    )
    assert bundle.platform == "instagram"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_partner_models.py -q`
Expected: FAIL because `app.models.partner` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create canonical partner tables for:
- accounts
- event records
- delivery bundles

Also add the Alembic revision and register the models in `app/models/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_partner_models.py -q`
Expected: PASS

---

### Task 2: Add Partner Routing Coverage

**Files:**
- Modify: `app/triggers/partner_events.py`
- Test: `tests/test_partner_routing.py`

- [ ] **Step 1: Write the failing test**

```python
from app.models.workflow import Platform
from app.triggers.partner_events import build_trigger_requests, normalize_partner_event


def test_registration_push_routes_to_x_linkedin_and_instagram():
    event = normalize_partner_event(
        "alliance_fastpitch",
        {
            "event_type": "registration_push",
            "external_event_id": "reg-1",
            "event_name": "Alliance Nationals",
            "registration_deadline": "2026-05-01",
        },
    )
    requests = build_trigger_requests(event)
    assert {request.platform for request in requests} == {Platform.X, Platform.LINKEDIN, Platform.INSTAGRAM}


def test_offer_update_routes_to_x_and_instagram():
    event = normalize_partner_event(
        "fss",
        {
            "event_type": "offer_update",
            "external_event_id": "offer-1",
            "athlete_name": "Jane Smith",
            "offer_school": "Oklahoma",
        },
    )
    requests = build_trigger_requests(event)
    assert {request.platform for request in requests} == {Platform.X, Platform.INSTAGRAM}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_partner_routing.py -q`
Expected: FAIL because the event types and routing are missing.

- [ ] **Step 3: Write minimal implementation**

Add:
- `offer_update`
- `registration_push`
- `event_promotion`

and route them through the correct partner platform sets.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_partner_routing.py -q`
Expected: PASS

---

### Task 3: Add Partner Intake Service

**Files:**
- Create: `app/services/partner_intake_service.py`
- Test: `tests/test_partner_service.py`

- [ ] **Step 1: Write the failing test**

```python
import uuid
from unittest.mock import MagicMock

from app.services.partner_intake_service import PartnerIntakeService


def test_ingest_webhook_creates_partner_event_and_trigger(monkeypatch):
    db = MagicMock()
    service = PartnerIntakeService(db)
    monkeypatch.setattr(service, "_resolve_partner", lambda slug: type("Partner", (), {"id": uuid.uuid4(), "slug": slug, "display_name": "Alliance Fastpitch"})())
    monkeypatch.setattr(service, "_route_event", lambda partner, payload: [{"workflow_slug": "partner-alliance-assessment-x"}])
    result = service.ingest_webhook("alliance_fastpitch", {"event_type": "assessment_completed", "external_event_id": "evt-1"})
    assert result["partner_slug"] == "alliance_fastpitch"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_partner_service.py -q`
Expected: FAIL because the service does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement intake methods for:
- webhook submissions
- portal submissions
- event-record listing
- partner-account listing

The service should create a canonical `PartnerEventRecord` before routing.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_partner_service.py -q`
Expected: PASS

---

### Task 4: Add Partner Delivery Service

**Files:**
- Create: `app/services/partner_delivery_service.py`
- Modify: `app/services/trigger_engine.py`
- Test: `tests/test_partner_service.py`

- [ ] **Step 1: Write the failing test**

```python
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.partner_delivery_service import PartnerDeliveryService


def test_create_bundle_from_partner_draft():
    db = MagicMock()
    service = PartnerDeliveryService(db)
    draft = SimpleNamespace(id=uuid.uuid4(), content="Caption", hashtags=["#Alliance"], platform=SimpleNamespace(value="instagram"))
    partner = SimpleNamespace(id=uuid.uuid4(), display_name="Alliance Fastpitch")
    event = SimpleNamespace(id=uuid.uuid4(), event_type="leaderboard_published")
    bundle = service.build_bundle(partner, event, draft, asset_ids=[])
    assert bundle.caption == "Caption"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_partner_service.py -q`
Expected: FAIL because the bundle service does not exist.

- [ ] **Step 3: Write minimal implementation**

Create partner delivery bundles from canonical partner-triggered drafts and connect them to the event record.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_partner_service.py -q`
Expected: PASS

---

### Task 5: Persist Partner Intent And Provenance

**Files:**
- Modify: `app/models/review.py`
- Modify: `app/services/workflow_engine.py`
- Modify: `app/services/prompt_assembler.py`
- Test: `tests/test_partner_service.py`

- [ ] **Step 1: Write the failing test**

```python
from app.models.review import DraftVariant


def test_partner_draft_has_partner_intent_and_metadata():
    draft = DraftVariant(intent="partner", partner_slug="alliance_fastpitch", source_event_type="assessment_completed")
    assert draft.intent == "partner"
    assert draft.partner_slug == "alliance_fastpitch"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_partner_service.py -q`
Expected: FAIL because canonical drafts do not store partner intent/provenance.

- [ ] **Step 3: Write minimal implementation**

Add canonical fields for:
- `intent`
- `partner_slug`
- `partner_name`
- `source_event_type`
- `source_event_id`

Write them during partner-triggered workflow execution.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_partner_service.py -q`
Expected: PASS

---

### Task 6: Add Partner API Routes

**Files:**
- Create: `app/api/partner_routes.py`
- Modify: `app/main.py`
- Test: `tests/test_partner_routes.py`

- [ ] **Step 1: Write the failing test**

```python
from app.main import app


def test_partner_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/control-room/partners" in paths
    assert "/api/control-room/partners/{partner_slug}/events" in paths
    assert "/api/control-room/partners/bundles" in paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_partner_routes.py -q`
Expected: FAIL because the routes do not exist.

- [ ] **Step 3: Write minimal implementation**

Add API routes for:
- partner listing
- partner event ingestion
- partner event listing
- bundle listing
- bundle delivery-status updates

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_partner_routes.py -q`
Expected: PASS

---

### Task 7: Add Control-Room Partner Hub

**Files:**
- Create: `app/web/templates/partners.html`
- Create: `app/web/templates/partials/partner_event_result.html`
- Create: `app/web/templates/partials/partner_bundle_result.html`
- Modify: `app/web/routes.py`
- Modify: `app/web/templates/base.html`
- Test: `tests/test_web_partners_view.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_partners_view_renders_events_and_bundles(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_partner_dashboard",
        lambda db: {
            "partners": [{"slug": "alliance-fastpitch", "display_name": "Alliance Fastpitch"}],
            "events": [{"event_type": "assessment_completed", "partner_name": "Alliance Fastpitch"}],
            "bundles": [{"platform": "instagram", "partner_name": "Alliance Fastpitch"}],
        },
    )
    response = client.get("/control-room/partners")
    assert response.status_code == 200
    assert "Alliance Fastpitch" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_partners_view.py -q`
Expected: FAIL because the partner hub does not exist.

- [ ] **Step 3: Write minimal implementation**

Add the control-room partner hub and navigation entry.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_partners_view.py -q`
Expected: PASS

---

### Task 8: Add Partner Portal

**Files:**
- Create: `app/web/partner_portal.py`
- Create: `app/web/templates/partner_portal_login.html`
- Create: `app/web/templates/partner_portal_submit.html`
- Create: `app/web/templates/partner_portal_packages.html`
- Modify: `app/main.py`
- Test: `tests/test_partner_portal_view.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_partner_portal_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/partner-portal/login" in paths
    assert "/partner-portal/submit" in paths
    assert "/partner-portal/packages" in paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_partner_portal_view.py -q`
Expected: FAIL because the portal routes do not exist.

- [ ] **Step 3: Write minimal implementation**

Add a simple session-backed partner portal using partner account credentials.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_partner_portal_view.py -q`
Expected: PASS

---

### Task 9: Run Partner Regression And Full Suite

**Files:**
- Test: `tests/test_partner_models.py`
- Test: `tests/test_partner_service.py`
- Test: `tests/test_partner_routes.py`
- Test: `tests/test_partner_portal_view.py`
- Test: `tests/test_web_partners_view.py`
- Test: `tests/test_partner_routing.py`

- [ ] **Step 1: Run the partner suite**

Run: `pytest tests/test_partner_models.py tests/test_partner_service.py tests/test_partner_routes.py tests/test_partner_portal_view.py tests/test_web_partners_view.py tests/test_partner_routing.py -q`
Expected: PASS

- [ ] **Step 2: Run the broader control-room suite**

Run: `pytest tests/test_control_room_api.py tests/test_trigger_api.py tests/test_scheduler.py tests/test_web_manual_view.py tests/test_web_calendar_view.py tests/test_web_analytics_view.py -q`
Expected: PASS

- [ ] **Step 3: Run the full repository suite**

Run: `pytest -q`
Expected: PASS

---

## Self-Review

- Spec coverage: this plan covers the missing partner-engine slice from the blueprint: intake, portal, routing, delivery, hub, and partner intent persistence.
- Placeholder scan: there are no `TODO` or `TBD` placeholders in task steps.
- Type consistency: the canonical partner flow is centered on `PartnerAccount`, `PartnerEventRecord`, `PartnerDeliveryBundle`, `TriggerEvent`, `ContentJob`, and `DraftVariant`.
