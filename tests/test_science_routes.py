import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.science_routes as science_routes
from app.database import get_db


def _client():
    app = FastAPI()
    app.include_router(science_routes.router)
    return TestClient(app, raise_server_exceptions=False), app


def test_science_routes_are_registered():
    paths = {route.path for route in science_routes.router.routes}
    assert "/api/control-room/science" in paths
    assert "/api/control-room/science/generate" in paths


def test_generate_science_route_returns_record(monkeypatch):
    client, app = _client()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {"records": [], "counts": {"total": 0}}

        def generate_science_content(self, science_type, **kwargs):
            assert science_type == "advisor_spotlight"
            return {
                "id": str(uuid.uuid4()),
                "science_type": science_type,
                "status": "review_ready",
                "title": "Advisor Spotlight: Dr. Ed Levine",
                "summary": "Advisor spotlight content focused on the science team.",
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(science_routes, "ScienceCredibilityService", FakeService)

    response = client.post(
        "/api/control-room/science/generate",
        headers={"Authorization": "Bearer test-secret-key"},
        json={
            "science_type": "advisor_spotlight",
            "platform": "linkedin",
            "advisor_name": "Dr. Ed Levine",
            "topic": "Validation matters",
            "audience": "college coaches",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["science_type"] == "advisor_spotlight"
    assert payload["status"] == "review_ready"


def test_generate_science_route_accepts_form_post(monkeypatch):
    client, app = _client()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {"records": [], "counts": {"total": 0}}

        def generate_science_content(self, science_type, **kwargs):
            assert kwargs["advisor_name"] == "Dr. Ed Levine"
            assert kwargs["topic"] == "Validation matters"
            return {
                "id": str(uuid.uuid4()),
                "science_type": science_type,
                "status": "review_ready",
                "title": "Advisor Spotlight: Dr. Ed Levine",
                "summary": "Advisor spotlight content focused on the science team.",
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(science_routes, "ScienceCredibilityService", FakeService)

    response = client.post(
        "/api/control-room/science/generate",
        headers={"Authorization": "Bearer test-secret-key"},
        data={
            "science_type": "advisor_spotlight",
            "platform": "linkedin",
            "advisor_name": "Dr. Ed Levine",
            "topic": "Validation matters",
            "audience": "college coaches",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["title"] == "Advisor Spotlight: Dr. Ed Levine"


def test_generate_science_route_returns_htmx_fragment(monkeypatch):
    client, app = _client()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {"records": [], "counts": {"total": 0}}

        def generate_science_content(self, science_type, **kwargs):
            return {
                "id": str(uuid.uuid4()),
                "science_type": science_type,
                "status": "review_ready",
                "title": "Advisor Spotlight: Dr. Ed Levine",
                "summary": "Advisor spotlight content focused on the science team.",
                "workflow_slug": "science-advisor_spotlight-linkedin",
                "job_status": "completed",
                "source_focus": "science team credibility",
                "draft_id": "draft-1",
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(science_routes, "ScienceCredibilityService", FakeService)

    response = client.post(
        "/api/control-room/science/generate",
        headers={"Authorization": "Bearer test-secret-key", "HX-Request": "true"},
        data={
            "science_type": "advisor_spotlight",
            "platform": "linkedin",
            "advisor_name": "Dr. Ed Levine",
            "topic": "Validation matters",
            "audience": "college coaches",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Advisor Spotlight: Dr. Ed Levine" in response.text
    assert "Workflow job: completed" in response.text
    assert "draft-1" in response.text
