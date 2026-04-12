import uuid

from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_automatic_view_renders_workflow_cards(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_automatic_workflow_cards",
        lambda db: [
            {
                "workflow_id": str(uuid.uuid4()),
                "workflow_name": "Instagram Auto Workflow",
                "platform": "instagram",
                "mode": "automatic",
                "timezone": "America/Toronto",
                "health_status": "healthy",
                "next_trigger_label": "Apr 06, 09:00",
                "publish_time_label": "09:30",
                "queued_draft_count": 2,
                "last_success_label": "Apr 05, 09:32",
                "last_error": None,
                "drafts": [
                    {
                        "id": str(uuid.uuid4()),
                        "content": "Carousel draft preview",
                        "scheduled_label": "Apr 06, 09:30",
                        "trigger_label": "Calendar Trigger",
                        "state": "automatic_ready",
                    }
                ],
            }
        ],
        raising=False,
    )

    response = client.get("/control-room/automatic")

    assert response.status_code == 200
    assert "Instagram Auto Workflow" in response.text
    assert "Next Trigger" in response.text
    assert "Queued Drafts" in response.text
    assert "Pause" in response.text
    assert "Move to Manual" in response.text


def test_home_view_shows_scheduler_health_widgets(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_home_summary",
        lambda db: {
            "manual_count": 5,
            "auto_count": 3,
            "published_count": 10,
            "rejected_count": 1,
            "expired_count": 2,
            "failed_count": 1,
            "trigger_count": 8,
            "workflow_count": 4,
            "paused_workflow_count": 1,
            "unhealthy_workflow_count": 2,
            "upcoming_auto_count": 6,
        },
        raising=False,
    )

    response = client.get("/control-room/")

    assert response.status_code == 200
    # The home template renders paused_workflow_count inline as "N workflows paused"
    assert "workflows paused" in response.text
    # The dashboard tab badge reflects manual_count (review count)
    assert "Dashboard" in response.text
