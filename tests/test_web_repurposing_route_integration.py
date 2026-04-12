from fastapi.testclient import TestClient

import app.api.repurposing_routes as repurposing_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_repurposing_web_view_renders_dashboard(monkeypatch):
    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self, limit=50):
            return {
                "sources": [
                    {
                        "title": "Pressure Performance",
                        "source_kind": "manual",
                        "channel": "linkedin",
                    }
                ],
                "derivatives": [
                    {
                        "title": "LinkedIn derivative",
                        "channel": "linkedin",
                        "status": "manual_ready",
                        "content": "Derivative body",
                    }
                ],
                "runs": [{"id": "run-1", "status": "completed"}],
            }

    monkeypatch.setattr(repurposing_routes, "RepurposingService", FakeService)

    response = client.get("/control-room/repurposing")

    assert response.status_code == 200
    assert "Repurposing Engine" in response.text
    assert "Pressure Performance" in response.text
    assert "LinkedIn derivative" in response.text
