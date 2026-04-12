import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.repurposing_routes as repurposing_routes
from app.database import get_db


def _client():
    app = FastAPI()
    app.include_router(repurposing_routes.router)
    return TestClient(app, raise_server_exceptions=False), app


def test_repurposing_routes_are_registered():
    paths = {route.path for route in repurposing_routes.router.routes}
    assert "/api/control-room/repurposing" in paths
    assert "/api/control-room/repurposing/sources/{source_kind}/{source_id}/fanout" in paths


def test_list_repurposing_dashboard_returns_sources_and_derivatives(monkeypatch):
    client, app = _client()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self, limit=50):
            return {
                "sources": [{"id": str(uuid.uuid4()), "title": "Pressure Performance"}],
                "derivatives": [{"id": str(uuid.uuid4()), "channel": "linkedin"}],
                "runs": [{"id": str(uuid.uuid4()), "status": "completed"}],
            }

        def fan_out_source(self, source, channels=None):
            return {}

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(repurposing_routes, "RepurposingService", FakeService)

    response = client.get(
        "/api/control-room/repurposing",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"][0]["title"] == "Pressure Performance"
    assert payload["derivatives"][0]["channel"] == "linkedin"


def test_fanout_route_returns_html_fragment(monkeypatch):
    client, app = _client()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self, limit=50):
            return {"sources": [], "derivatives": [], "runs": []}

        def fan_out_source(self, source, channels=None):
            assert source.source_kind == "manual"
            assert source.source_id == "seed-1"
            assert source.title == "Pressure Performance"
            assert source.channels == ["x", "linkedin"]
            return {
                "source_id": str(uuid.uuid4()),
                "source_kind": source.source_kind,
                "source_title": source.title,
                "derivatives": [
                    {"title": "X draft", "channel": "x", "status": "manual_ready", "content": "Draft body"},
                    {"title": "LinkedIn draft", "channel": "linkedin", "status": "manual_ready", "content": "Draft body"},
                ],
                "run_id": str(uuid.uuid4()),
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(repurposing_routes, "RepurposingService", FakeService)

    response = client.post(
        "/api/control-room/repurposing/sources/manual/seed-1/fanout",
        headers={
            "Authorization": "Bearer test-secret-key",
            "HX-Request": "true",
        },
        data={
            "title": "Pressure Performance",
            "source_text": "A nucleus post about translating pressure into proof.",
            "source_platform": "linkedin",
            "channels": "x,linkedin",
            "actor": "planner",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Repurposing Run" in response.text
    assert "X draft" in response.text
    assert "LinkedIn draft" in response.text
