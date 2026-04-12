from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.ugc_routes as ugc_routes
from app.database import get_db


def _build_client():
    app = FastAPI()
    app.include_router(ugc_routes.web_router)

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    app.dependency_overrides[get_db] = fake_get_db
    return app, TestClient(app, raise_server_exceptions=False)


def test_ugc_web_view_renders_requests_and_submissions(monkeypatch):
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
                "submissions": [
                    {
                        "id": "sub-1",
                        "athlete_name": "Jane Smith",
                        "score_tier": "Silver",
                        "video_url": "https://video.example.com/1",
                        "status": "accepted",
                    }
                ],
                "request_count": 1,
                "submission_count": 1,
            }

    monkeypatch.setattr(ugc_routes, "UGCService", FakeService)

    response = client.get("/control-room/ugc")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "UGC" in response.text
    assert "Jane Smith" in response.text
    assert "https://video.example.com/1" in response.text


def test_ugc_web_request_fragment_renders_result(monkeypatch):
    app, client = _build_client()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def create_testimonial_request(self, **kwargs):
            return {
                "id": "req-2",
                "athlete_name": kwargs["athlete_name"],
                "score_tier": "Certified",
                "subject": "Jane Smith, share your clutch story",
                "request_copy": "Please send a short testimonial.",
                "status": "sent",
            }

    monkeypatch.setattr(ugc_routes, "UGCService", FakeService)

    response = client.post(
        "/control-room/ugc/requests",
        data={
            "athlete_name": "Jane Smith",
            "score": 780,
            "sport": "softball",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Jane Smith" in response.text
    assert "Please send a short testimonial." in response.text

