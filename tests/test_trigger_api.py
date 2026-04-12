import uuid

from fastapi.testclient import TestClient

import app.api.trigger_routes as trigger_routes
from app.database import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_partner_webhook_requires_auth():
    response = client.post("/webhooks/partners/alliance_fastpitch/events", json={})
    assert response.status_code == 403


def test_trigger_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/webhooks/partners/{partner_slug}/events" in paths
    assert "/triggers/events" in paths


def test_partner_webhook_returns_execution_summary(monkeypatch):
    def fake_get_db():
        yield object()

    def fake_ingest(partner_slug, payload, db):
        assert partner_slug == "alliance_fastpitch"
        assert payload["event_type"] == "commitment_update"
        return [
            {
                "trigger_event_id": str(uuid.uuid4()),
                "platform": "x",
                "status": "manual_ready",
                "workflow_slug": "partner-alliance-fastpitch-commitment-update-x",
            }
        ]

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(trigger_routes, "ingest_partner_webhook", fake_ingest)
    response = client.post(
        "/webhooks/partners/alliance_fastpitch/events",
        headers={"Authorization": "Bearer test-secret-key"},
        json={
            "event_type": "commitment_update",
            "external_event_id": "evt-commit-1",
            "athlete_name": "Jane Smith",
            "commitment_school": "Oklahoma",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["platform"] == "x"
    assert payload["results"][0]["status"] == "manual_ready"
