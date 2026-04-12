import uuid

from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_competitors_view_renders_sources_and_signals(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_competitor_dashboard",
        lambda db: {
            "sources": [
                {
                    "id": str(uuid.uuid4()),
                    "slug": "rival-brand",
                    "display_name": "Rival Brand",
                    "platform": "linkedin",
                    "source_url": "https://example.com/rival",
                    "active": True,
                }
            ],
            "signals": [
                {
                    "id": str(uuid.uuid4()),
                    "source_name": "Rival Brand",
                    "signal_type": "positioning_shift",
                    "summary": "Moved toward pressure-data messaging",
                    "severity": "medium",
                    "reaction_angle": "Lead with proof-first coach evidence.",
                }
            ],
        },
    )

    response = client.get("/control-room/competitors")

    assert response.status_code == 200
    assert "Competitors" in response.text
    assert "Rival Brand" in response.text
    assert "Moved toward pressure-data messaging" in response.text
    assert "Lead with proof-first coach evidence." in response.text


def test_competitor_signal_action_fragment_renders_result(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "respond_to_competitor_signal_from_web",
        lambda db, signal_id, platform="linkedin", actor="analyst": {
            "workflow_slug": "competitor-response-linkedin",
            "status": "manual_ready",
            "trigger_event_id": str(uuid.uuid4()),
            "platform": platform,
        },
    )

    response = client.post(
        f"/control-room/competitors/signals/{uuid.uuid4()}/respond",
        data={"platform": "linkedin", "actor": "analyst"},
    )

    assert response.status_code == 200
    assert "competitor-response-linkedin" in response.text
    assert "manual_ready" in response.text

