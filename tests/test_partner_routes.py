import uuid

from fastapi.testclient import TestClient

import app.api.partner_routes as partner_routes
from app.database import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_partner_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/control-room/partners" in paths
    assert "/api/control-room/partners/{partner_slug}/events" in paths
    assert "/api/control-room/partners/bundles" in paths


def test_partner_event_ingest_returns_result(monkeypatch):
    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_partners(self):
            return []

        def list_events(self, partner_slug=None, limit=50):
            return []

        def list_bundles(self, partner_slug=None, limit=50):
            return []

        def ingest_webhook(self, partner_slug, payload):
            return {
                "partner_slug": partner_slug,
                "results": [{"workflow_slug": "partner-alliance-assessment-x", "status": "manual_ready"}],
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(partner_routes, "PartnerIntakeService", FakeService)

    response = client.post(
        "/api/control-room/partners/alliance_fastpitch/events",
        headers={"Authorization": "Bearer test-secret-key"},
        json={"event_type": "assessment_completed", "external_event_id": "evt-1"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["partner_slug"] == "alliance_fastpitch"


def test_partner_bundles_route_returns_bundles(monkeypatch):
    class FakeDB:
        pass

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_bundles(self, partner_slug=None, limit=50):
            return [
                {
                    "id": str(uuid.uuid4()),
                    "partner_name": "Alliance Fastpitch",
                    "platform": "instagram",
                    "status": "needs_review",
                }
            ]

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(partner_routes, "PartnerDeliveryService", FakeService)

    response = client.get(
        "/api/control-room/partners/bundles",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["bundles"][0]["partner_name"] == "Alliance Fastpitch"
