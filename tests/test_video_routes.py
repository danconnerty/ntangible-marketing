from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.video_routes as video_routes
from app.database import get_db


def _build_client(monkeypatch):
    app = FastAPI()
    app.include_router(video_routes.router)

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    app.dependency_overrides[get_db] = fake_get_db
    return app, TestClient(app, raise_server_exceptions=False)


def test_video_api_returns_dashboard(monkeypatch):
    app, client = _build_client(monkeypatch)

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {
                "briefs": [
                    {
                        "id": "brief-1",
                        "title": "Founder raw video brief",
                        "kind": "founder_raw",
                        "platform": "linkedin",
                        "brief_format": "founder_raw",
                        "status": "briefed",
                        "hook": "Open with the core point.",
                    }
                ],
                "count": 1,
            }

    monkeypatch.setattr(video_routes, "VideoContentService", FakeService)

    response = client.get("/api/control-room/video", headers={"Authorization": "Bearer test-secret-key"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["briefs"][0]["title"] == "Founder raw video brief"


def test_video_api_creates_brief(monkeypatch):
    app, client = _build_client(monkeypatch)

    class FakeService:
        def __init__(self, db):
            self.db = db

        def create_brief(self, **kwargs):
            assert kwargs["kind"] == "reel_from_static"
            assert kwargs["target_platform"] == "linkedin"
            return {
                "id": "brief-1",
                "title": "Reel from static proof",
                "kind": "reel_from_static",
                "platform": "linkedin",
                "brief_format": "reel",
                "status": "needs_review",
                "hook": "Turn this proof into a reel.",
                "script": "Hook: ...",
            }

    monkeypatch.setattr(video_routes, "VideoContentService", FakeService)

    response = client.post(
        "/api/control-room/video/briefs",
        headers={"Authorization": "Bearer test-secret-key"},
        json={
            "kind": "reel_from_static",
            "target_platform": "linkedin",
            "context": "Static proof point.",
            "source_mode": "manual",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["kind"] == "reel_from_static"
    assert response.json()["brief_format"] == "reel"

