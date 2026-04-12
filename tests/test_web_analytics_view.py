from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_analytics_page_renders_summary_sections(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_analytics_dashboard",
        lambda db, platform=None, workflow_slug=None, days=30: {
            "summary": {
                "promotion_confidence": 0.81,
                "publication_success_rate": 0.92,
                "approval_rate": 0.75,
                "rejection_rate": 0.10,
                "expiration_rate": 0.15,
                "average_content_score": 79.3,
                "recycle_candidate_count": 2,
            },
            "workflow_metrics": [
                {
                    "workflow_name": "Tuesday LinkedIn TL",
                    "workflow_slug": "tuesday-linkedin-tl",
                    "platform": "linkedin",
                    "trigger_type": "calendar",
                    "promotion_confidence": 0.81,
                    "publication_success_rate": 0.92,
                    "engagement_percentile": 0.66,
                    "record_count": 12,
                    "average_content_score": 81.2,
                    "recycle_candidate_count": 2,
                }
            ],
            "platform_metrics": [
                {
                    "platform": "linkedin",
                    "promotion_confidence": 0.81,
                    "publication_success_rate": 0.92,
                    "record_count": 12,
                    "average_content_score": 81.2,
                    "recycle_candidate_count": 2,
                }
            ],
            "recycle_candidates": [
                {
                    "workflow_name": "Tuesday LinkedIn TL",
                    "content_preview": "Pressure data beats vibes.",
                    "content_score": 82.4,
                    "score_label": "strong",
                }
            ],
            "filters": {"platform": platform, "workflow_slug": workflow_slug, "days": days},
        },
    )

    response = client.get("/control-room/analytics")

    assert response.status_code == 200
    assert "Overview" in response.text
    assert "Workflow Health" in response.text
    assert "Published Content" in response.text
    assert "Tuesday LinkedIn TL" in response.text
    assert "Competitor Monitor" in response.text


def test_analytics_page_loads_all_platforms_by_default(monkeypatch):
    captured: dict[str, object] = {}

    def fake_dashboard(db, platform=None, workflow_slug=None, days=30):
        captured["dashboard_platform"] = platform
        return {
            "summary": {
                "record_count": 2,
                "workflow_count": 2,
                "window_days": 30,
            },
            "workflow_metrics": [],
            "platform_metrics": [
                {"platform": "linkedin", "record_count": 1},
                {"platform": "instagram", "record_count": 1},
            ],
            "recycle_candidates": [],
            "filters": {"platform": platform, "workflow_slug": workflow_slug, "days": days},
        }

    def fake_recent_posts(db, *, platform=None, limit=20):
        captured["published_posts_platform"] = platform
        captured["published_posts_limit"] = limit
        return [
            {
                "id": "1",
                "platform": "linkedin",
                "workflow_name": "LinkedIn Workflow",
                "published_at": "2026-04-10T12:00:00",
                "content_preview": "LinkedIn post",
                "impressions": 0,
                "engagement_rate": 0.0,
                "content_score": 0.0,
                "recycle": False,
            },
            {
                "id": "2",
                "platform": "instagram",
                "workflow_name": "Instagram Workflow",
                "published_at": "2026-04-09T12:00:00",
                "content_preview": "Instagram post",
                "impressions": 0,
                "engagement_rate": 0.0,
                "content_score": 0.0,
                "recycle": False,
            },
        ]

    monkeypatch.setattr(web_routes, "load_analytics_dashboard", fake_dashboard)
    monkeypatch.setattr(web_routes, "_load_recent_published_posts", fake_recent_posts)
    monkeypatch.setattr(web_routes, "generate_weekly_digest", lambda db: {"total_posts": 0})
    monkeypatch.setattr(web_routes, "load_competitor_dashboard", lambda db: {"signals": []})
    monkeypatch.setattr(
        web_routes,
        "load_revenue_dashboard",
        lambda db: {"playbooks": [], "conversion_goals": [], "executions": []},
    )

    response = client.get("/control-room/analytics")

    assert response.status_code == 200
    assert captured["dashboard_platform"] is None
    assert captured["published_posts_platform"] is None
    assert captured["published_posts_limit"] == 100
    assert "LinkedIn Workflow" in response.text
    assert "Instagram Workflow" in response.text


def test_analytics_page_platform_chips_use_server_filters(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        web_routes,
        "load_analytics_dashboard",
        lambda db, platform=None, workflow_slug=None, days=30: {
            "summary": {"record_count": 1, "workflow_count": 1, "window_days": 30},
            "workflow_metrics": [],
            "platform_metrics": [{"platform": "linkedin", "record_count": 1}],
            "recycle_candidates": [],
            "filters": {"platform": platform, "workflow_slug": workflow_slug, "days": days},
        },
    )

    def fake_recent_posts(db, *, platform=None, limit=20):
        captured["published_posts_platform"] = platform
        captured["published_posts_limit"] = limit
        return [
            {
                "id": "1",
                "platform": "linkedin",
                "workflow_name": "LinkedIn Workflow",
                "published_at": "2026-04-10T12:00:00",
                "content_preview": "LinkedIn post",
                "impressions": 0,
                "engagement_rate": 0.0,
                "content_score": 0.0,
                "recycle": False,
            }
        ]

    monkeypatch.setattr(web_routes, "_load_recent_published_posts", fake_recent_posts)
    monkeypatch.setattr(web_routes, "generate_weekly_digest", lambda db: {"total_posts": 0})
    monkeypatch.setattr(web_routes, "load_competitor_dashboard", lambda db: {"signals": []})
    monkeypatch.setattr(
        web_routes,
        "load_revenue_dashboard",
        lambda db: {"playbooks": [], "conversion_goals": [], "executions": []},
    )

    response = client.get("/control-room/analytics?platform=linkedin")

    assert response.status_code == 200
    assert captured["published_posts_platform"] == "linkedin"
    assert captured["published_posts_limit"] == 100
    assert 'href="/control-room/analytics?platform=linkedin' in response.text
