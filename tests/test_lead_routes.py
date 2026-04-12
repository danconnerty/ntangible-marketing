import uuid

from fastapi.testclient import TestClient

import app.api.lead_routes as lead_routes
from app.database import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_lead_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/control-room/leads" in paths
    assert "/api/control-room/leads/{lead_id}/generate-content" in paths
    assert "/control-room/leads" in paths


def test_list_leads_returns_dashboard(monkeypatch):
    class FakeDB:
        pass

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {
                "leads": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "West Coast Academy",
                        "stage": "qualified",
                        "priority": "high",
                        "open_task_count": 2,
                    }
                ],
                "tasks": [],
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(lead_routes, "LeadNurtureService", FakeService)

    response = client.get(
        "/api/control-room/leads",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["leads"][0]["name"] == "West Coast Academy"


def test_generate_content_route_returns_trigger_result(monkeypatch):
    lead_id = uuid.uuid4()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def generate_content(self, incoming_lead_id, platform, actor="sales"):
            assert incoming_lead_id == lead_id
            assert platform == "linkedin"
            return {
                "workflow_slug": "lead-nurture-linkedin",
                "status": "manual_ready",
                "trigger_event_id": str(uuid.uuid4()),
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(lead_routes, "LeadNurtureService", FakeService)

    response = client.post(
        f"/api/control-room/leads/{lead_id}/generate-content",
        headers={"Authorization": "Bearer test-secret-key"},
        json={"platform": "linkedin", "actor": "sales"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_slug"] == "lead-nurture-linkedin"

