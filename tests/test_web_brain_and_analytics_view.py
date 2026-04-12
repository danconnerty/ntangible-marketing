from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_brain_view_renders_results(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_brain_results",
        lambda db, query="", bucket=None, platform=None, workflow_slug=None, limit=50: {
            "query": query,
            "items": [
                {
                    "title": "Top recruiting post",
                    "content": "Pressure data helps coaches trust their board.",
                    "bucket": "approved",
                    "platform": "linkedin",
                    "workflow_slug": "tuesday-linkedin-tl",
                }
            ],
            "summary": {"total": 1, "approved": 1, "rejected": 0},
        },
    )

    response = client.get("/control-room/brain")

    assert response.status_code == 200
    assert "Brain / History" in response.text
    assert "Top recruiting post" in response.text
    assert "approved" in response.text


def test_trigger_feed_view_renders_events(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_trigger_feed_items",
        lambda db, limit=50: [
            {
                "partner_slug": "alliance_fastpitch",
                "workflow_slug": "partner-alliance-commitment-x",
                "platform": "x",
                "external_event_type": "commitment_update",
                "processing_status": "processed",
                "draft_state": "manual_ready",
                "created_label": "Apr 06, 09:00",
            }
        ],
    )

    response = client.get("/control-room/triggers")

    assert response.status_code == 200
    assert "Trigger Feed" in response.text
    assert "alliance_fastpitch" in response.text
    assert "commitment_update" in response.text


def test_analytics_view_renders_workflow_summary(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_analytics_dashboard",
        lambda db, platform=None, workflow_slug=None, days=30: {
            "summary": {
                "promotion_confidence": 0.82,
                "publication_success_rate": 0.8,
                "approval_rate": 0.75,
                "rejection_rate": 0.15,
                "expiration_rate": 0.05,
                "record_count": 12,
                "workflow_count": 1,
                "window_days": 30,
                "promotion_recommendation": "candidate",
            },
            "workflow_metrics": [
                {
                    "workflow_name": "Tuesday LinkedIn TL",
                    "workflow_slug": "tuesday-linkedin-tl",
                    "platform": "linkedin",
                    "trigger_type": "calendar",
                    "publication_success_rate": 0.8,
                    "approval_rate": 0.75,
                    "engagement_percentile": 0.42,
                    "promotion_confidence": 0.82,
                    "record_count": 12,
                }
            ],
            "platform_metrics": [
                {
                    "platform": "linkedin",
                    "promotion_confidence": 0.82,
                    "publication_success_rate": 0.8,
                    "approval_rate": 0.75,
                    "record_count": 12,
                }
            ],
            "filters": {"platform": platform, "workflow_slug": workflow_slug, "days": days},
        },
    )

    response = client.get("/control-room/analytics")

    assert response.status_code == 200
    assert "Analytics" in response.text
    assert "Tuesday LinkedIn TL" in response.text
    assert "Confidence" in response.text
    assert "0.82" in response.text
