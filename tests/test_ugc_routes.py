from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.ugc_routes as ugc_routes
from app.database import get_db


def _build_client():
    app = FastAPI()
    app.include_router(ugc_routes.router)

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    app.dependency_overrides[get_db] = fake_get_db
    return app, TestClient(app, raise_server_exceptions=False)


def test_ugc_api_returns_dashboard(monkeypatch):
    app, client = _build_client()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {
                "requests": [
                    {
                        "id": "req-1",
                        "athlete_name": "Jane Smith",
                        "score_tier": "Certified",
                        "subject": "Jane Smith, share your clutch story",
                        "status": "sent",
                    }
                ],
                "submissions": [],
                "request_count": 1,
                "submission_count": 0,
            }

    monkeypatch.setattr(ugc_routes, "UGCService", FakeService)

    response = client.get("/api/control-room/ugc", headers={"Authorization": "Bearer test-secret-key"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["request_count"] == 1
    assert response.json()["requests"][0]["athlete_name"] == "Jane Smith"


def test_ugc_api_creates_testimonial_request(monkeypatch):
    app, client = _build_client()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def create_testimonial_request(self, **kwargs):
            assert kwargs["score"] == 780
            return {
                "id": "req-1",
                "athlete_name": kwargs["athlete_name"],
                "score_tier": "Certified",
                "subject": "Jane Smith, share your clutch story",
                "request_copy": "Please send a short testimonial.",
                "graphic_url": "https://cdn.example.com/score.png",
                "status": "sent",
            }

    monkeypatch.setattr(ugc_routes, "UGCService", FakeService)

    response = client.post(
        "/api/control-room/ugc/requests",
        headers={"Authorization": "Bearer test-secret-key"},
        json={
            "athlete_name": "Jane Smith",
            "score": 780,
            "athlete_email": "jane@example.com",
            "parent_name": "Pat Smith",
            "parent_email": "pat@example.com",
            "sport": "softball",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert response.json()["graphic_url"] == "https://cdn.example.com/score.png"


def test_ugc_api_creates_submission(monkeypatch):
    app, client = _build_client()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def submit_testimonial(self, **kwargs):
            assert kwargs["consent_share"] is True
            return {
                "id": "sub-1",
                "athlete_name": kwargs["athlete_name"],
                "score_tier": "Silver",
                "video_url": kwargs["video_url"],
                "status": "accepted",
                "video_brief": {"id": "brief-1", "title": "Jane Smith testimonial video brief"},
            }

    monkeypatch.setattr(ugc_routes, "UGCService", FakeService)

    response = client.post(
        "/api/control-room/ugc/submissions",
        headers={"Authorization": "Bearer test-secret-key"},
        json={
            "athlete_name": "Jane Smith",
            "score": 810,
            "video_url": "https://video.example.com/1",
            "consent_athlete": True,
            "consent_parent": False,
            "consent_share": True,
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["video_brief"]["title"] == "Jane Smith testimonial video brief"

