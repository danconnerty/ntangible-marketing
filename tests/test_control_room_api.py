import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.api.control_room_routes as control_room_routes
from app.database import get_db
from app.main import app
from app.models.review import DraftVariant
from app.models.workflow import DraftState, Platform
from app.models.workflow import WorkflowMode


client = TestClient(app, raise_server_exceptions=False)


def test_control_room_api_routes_are_namespaced():
    paths = {route.path for route in app.routes}

    assert "/api/control-room/manual" in paths
    assert "/api/control-room/automatic" in paths
    assert "/api/control-room/automatic/workflows" in paths
    assert "/api/control-room/drafts/{draft_id}" in paths
    assert "/api/control-room/drafts/{draft_id}/action" in paths
    assert "/api/control-room/workflows/{workflow_id}/pause" in paths
    assert "/api/control-room/workflows/{workflow_id}/resume" in paths
    assert "/api/control-room/workflows/{workflow_id}/move-to-manual" in paths
    assert "/api/control-room/scheduler/status" in paths
    assert "/api/analytics/summary" in paths
    assert "/api/analytics/publications/{publication_id}" in paths
    assert "/api/control-room/campaigns" in paths
    assert "/api/control-room/competitors" in paths
    assert "/api/control-room/leads" in paths
    assert "/api/control-room/revenue" in paths
    assert "/api/control-room/blog" in paths
    assert "/api/control-room/science" in paths
    assert "/api/control-room/repurposing" in paths
    assert "/api/control-room/video" in paths
    assert "/api/control-room/ugc" in paths
    assert "/api/control-room/sports" in paths
    assert "/control-room/manual" in paths
    assert "/control-room/analytics" in paths
    assert "/control-room/campaigns" in paths
    assert "/control-room/competitors" in paths
    assert "/control-room/leads" in paths
    assert "/control-room/revenue" in paths
    assert "/control-room/expansion" in paths
    assert "/control-room/blog" in paths
    assert "/control-room/science" in paths
    assert "/control-room/repurposing" in paths
    assert "/control-room/video" in paths
    assert "/control-room/ugc" in paths
    assert "/control-room/sports" in paths


def test_pause_workflow_endpoint_returns_updated_state(monkeypatch):
    workflow_id = uuid.uuid4()
    paused_at = datetime(2026, 4, 6, 13, 30, tzinfo=timezone.utc)

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    def fake_set_pause_state(db, incoming_workflow_id, *, paused):
        assert incoming_workflow_id == str(workflow_id)
        assert paused is True
        return SimpleNamespace(
            id=workflow_id,
            mode=WorkflowMode.AUTOMATIC,
            health_status="paused",
            paused_at=paused_at,
        )

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(
        control_room_routes,
        "set_workflow_pause_state",
        fake_set_pause_state,
        raising=False,
    )

    response = client.post(
        f"/api/control-room/workflows/{workflow_id}/pause",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "workflow_id": str(workflow_id),
        "mode": "automatic",
        "health_status": "paused",
        "paused_at": paused_at.isoformat(),
    }


def test_list_automatic_workflows_returns_workflow_cards(monkeypatch):
    workflow_id = uuid.uuid4()

    def fake_get_db():
        yield object()

    def fake_list_workflows(db):
        return [
            {
                "workflow_id": str(workflow_id),
                "workflow_name": "Instagram Auto Workflow",
                "platform": "instagram",
                "mode": "automatic",
                "timezone": "America/Toronto",
                "health_status": "healthy",
                "queued_draft_count": 2,
                "drafts": [],
            }
        ]

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(
        control_room_routes,
        "list_automatic_workflow_cards",
        fake_list_workflows,
        raising=False,
    )

    response = client.get(
        "/api/control-room/automatic/workflows",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["workflows"][0]["workflow_name"] == "Instagram Auto Workflow"
    assert payload["workflows"][0]["queued_draft_count"] == 2


def test_scheduler_status_endpoint_returns_phase7_rollup(monkeypatch):
    def fake_get_db():
        yield object()

    def fake_scheduler_status(db):
        return {
            "paused_workflows": 1,
            "unhealthy_workflows": 2,
            "upcoming_24h": 4,
            "due_rules": 3,
            "due_drafts": 2,
        }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(
        control_room_routes,
        "build_scheduler_status",
        fake_scheduler_status,
        raising=False,
    )

    response = client.get(
        "/api/control-room/scheduler/status",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["paused_workflows"] == 1
    assert response.json()["upcoming_24h"] == 4


def test_serialize_draft_includes_newsletter_metadata():
    draft = DraftVariant(
        id=uuid.uuid4(),
        content_job_id=uuid.uuid4(),
        platform=Platform.NEWSLETTER,
        content="Newsletter body",
        hashtags=[],
        state=DraftState.MANUAL_READY,
        timezone="America/Toronto",
        compliance_result={
            "subject": "April pressure data coaches should use",
            "preview_text": "What the latest dataset changed.",
            "segment": "coaches_front_offices",
        },
    )

    payload = control_room_routes._serialize_draft(draft)

    assert payload["newsletter_subject"] == "April pressure data coaches should use"
    assert payload["newsletter_preview_text"] == "What the latest dataset changed."
    assert payload["newsletter_segment"] == "coaches_front_offices"
