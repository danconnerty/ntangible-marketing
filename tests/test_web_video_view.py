from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.video_routes as video_routes
from app.database import get_db


def _build_client():
    app = FastAPI()
    app.include_router(video_routes.web_router)

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    app.dependency_overrides[get_db] = fake_get_db
    return app, TestClient(app, raise_server_exceptions=False)


def test_video_web_view_renders_recent_briefs(monkeypatch):
    app, client = _build_client()

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

    response = client.get("/control-room/video")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Video" in response.text
    assert "Founder raw video brief" in response.text
    assert "Open with the core point." in response.text


def test_video_web_brief_fragment_renders_result(monkeypatch):
    app, client = _build_client()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def create_brief(self, **kwargs):
            return {
                "id": "brief-2",
                "title": "Reel from static proof",
                "kind": "reel_from_static",
                "platform": "linkedin",
                "brief_format": "reel",
                "status": "needs_review",
                "hook": "Turn this proof into a reel.",
                "script": "Hook: Turn this proof into a reel.",
            }

    monkeypatch.setattr(video_routes, "VideoContentService", FakeService)

    response = client.post(
        "/control-room/video/briefs",
        data={
            "kind": "reel_from_static",
            "target_platform": "linkedin",
            "context": "Static proof point.",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Reel from static proof" in response.text
    assert "Turn this proof into a reel." in response.text

