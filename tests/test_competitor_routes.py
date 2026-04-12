import uuid

from fastapi.testclient import TestClient

import app.api.competitor_routes as competitor_routes
from app.database import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_competitor_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/control-room/competitors" in paths
    assert "/api/control-room/competitors/observations" in paths
    assert "/api/control-room/competitors/signals/{signal_id}/respond" in paths


def test_competitor_observation_ingest_returns_signal(monkeypatch):
    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {"sources": [], "signals": []}

        def ingest_observation(self, payload):
            return {
                "signal_id": str(uuid.uuid4()),
                "signal_type": "positioning_shift",
                "severity": "medium",
                "summary": payload["headline"],
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(competitor_routes, "CompetitorService", FakeService)

    response = client.post(
        "/api/control-room/competitors/observations",
        headers={"Authorization": "Bearer test-secret-key"},
        json={
            "source_slug": "rival-brand",
            "headline": "Pressure is trainable",
            "url": "https://example.com/post",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["signal_type"] == "positioning_shift"
    assert payload["severity"] == "medium"


def test_competitor_respond_endpoint_returns_trigger_result(monkeypatch):
    signal_id = uuid.uuid4()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def create_response_trigger(self, incoming_signal_id, platform, actor="analyst"):
            assert incoming_signal_id == signal_id
            assert platform == "linkedin"
            return {
                "workflow_slug": "competitor-response-linkedin",
                "status": "manual_ready",
                "trigger_event_id": str(uuid.uuid4()),
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(competitor_routes, "CompetitorService", FakeService)

    response = client.post(
        f"/api/control-room/competitors/signals/{signal_id}/respond",
        headers={"Authorization": "Bearer test-secret-key"},
        json={"platform": "linkedin", "actor": "analyst"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_slug"] == "competitor-response-linkedin"
    assert payload["status"] == "manual_ready"

