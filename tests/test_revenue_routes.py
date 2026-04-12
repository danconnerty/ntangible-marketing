import uuid

from fastapi.testclient import TestClient

import app.api.revenue_routes as revenue_routes
from app.database import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_revenue_routes_are_registered():
    paths = {route.path for route in app.routes}

    assert "/api/control-room/revenue" in paths
    assert "/api/control-room/revenue/playbooks/{playbook_slug}/run" in paths
    assert "/api/control-room/revenue/conversions" in paths


def test_revenue_dashboard_api_returns_playbooks(monkeypatch):
    class FakeDB:
        pass

    def fake_get_db():
        yield FakeDB()

    class FakeRevenueService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {
                "playbooks": [{"slug": "alliance-registration-push", "name": "Alliance Registration Push"}],
                "executions": [],
                "conversion_goals": [],
                "conversion_events": [],
                "sales_packages": [],
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(revenue_routes, "RevenueService", FakeRevenueService)
    response = client.get(
        "/api/control-room/revenue",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["playbooks"][0]["slug"] == "alliance-registration-push"


def test_run_revenue_playbook_api_returns_summary(monkeypatch):
    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeRevenueService:
        def __init__(self, db):
            self.db = db

        def run_playbook_by_slug(self, playbook_slug, *, actor, source_kind, source_id, context=None):
            assert playbook_slug == "alliance-registration-push"
            assert actor == "sales"
            assert source_kind == "partner_event"
            assert source_id == "evt-1"
            return {
                "playbook_slug": playbook_slug,
                "intent": "revenue",
                "status": "completed",
                "sales_package_count": 1,
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(revenue_routes, "RevenueService", FakeRevenueService)
    response = client.post(
        "/api/control-room/revenue/playbooks/alliance-registration-push/run",
        headers={"Authorization": "Bearer test-secret-key"},
        json={"actor": "sales", "source_kind": "partner_event", "source_id": "evt-1", "context": {"cta": "Register"}},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["playbook_slug"] == "alliance-registration-push"


def test_record_conversion_event_api_returns_saved_event(monkeypatch):
    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeRevenueService:
        def __init__(self, db):
            self.db = db

        def record_conversion_event(self, **kwargs):
            return {
                "id": str(uuid.uuid4()),
                "goal_slug": kwargs["goal_slug"],
                "metric_value": kwargs["metric_value"],
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(revenue_routes, "RevenueService", FakeRevenueService)
    response = client.post(
        "/api/control-room/revenue/conversions",
        headers={"Authorization": "Bearer test-secret-key"},
        json={
            "goal_slug": "alliance-registration-completions",
            "external_event_id": "conv-1",
            "source_kind": "partner_event",
            "source_reference": "evt-1",
            "metric_value": 1,
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["goal_slug"] == "alliance-registration-completions"
