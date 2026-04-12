from fastapi.testclient import TestClient

import app.api.science_routes as science_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_science_web_view_renders_records(monkeypatch):
    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self):
            return {
                "records": [
                    {
                        "science_type": "advisor_spotlight",
                        "title": "Advisor Spotlight: Dr. Ed Levine",
                        "summary": "Advisor spotlight content focused on the science team.",
                        "workflow_slug": "science-advisor_spotlight-linkedin",
                        "status": "review_ready",
                    }
                ],
                "counts": {"total": 1},
            }

    monkeypatch.setattr(science_routes, "ScienceCredibilityService", FakeService)

    response = client.get("/control-room/science")

    assert response.status_code == 200
    assert "Science Credibility" in response.text
    assert "Advisor Spotlight: Dr. Ed Levine" in response.text
    assert "science-advisor_spotlight-linkedin" in response.text
