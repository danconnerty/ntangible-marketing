from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_revenue_view_renders_playbooks_and_goals(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_revenue_dashboard",
        lambda db: {
            "playbooks": [
                {
                    "slug": "alliance-registration-push",
                    "name": "Alliance Registration Push",
                    "playbook_type": "registration_push",
                    "persona": "event_operator",
                    "offer": "Register now",
                    "cta": "Reserve your spot",
                    "active": True,
                }
            ],
            "executions": [],
            "conversion_goals": [
                {
                    "slug": "alliance-registration-completions",
                    "name": "Alliance Registration Completions",
                    "metric_type": "registrations",
                }
            ],
            "conversion_events": [],
            "sales_packages": [],
        },
    )
    monkeypatch.setattr(
        web_routes,
        "load_lead_dashboard",
        lambda db: {"leads": [], "tasks": []},
    )
    monkeypatch.setattr(
        web_routes,
        "generate_weekly_digest",
        lambda db: {"intent_split": {"revenue": 28.0, "brand": 50.0, "partner": 22.0}, "total_posts": 10},
    )

    response = client.get("/control-room/revenue")

    assert response.status_code == 200
    assert "Revenue" in response.text
    assert "Alliance Registration Push" in response.text
    assert "Alliance Registration Completions" in response.text


def test_revenue_run_fragment_renders_result(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "run_revenue_playbook_from_web",
        lambda db, playbook_slug, actor="sales", source_kind="manual", source_id="manual-run", context=None: {
            "playbook_slug": playbook_slug,
            "intent": "revenue",
            "status": "completed",
            "sales_package_count": 1,
        },
    )

    response = client.post(
        "/control-room/revenue/playbooks/alliance-registration-push/run",
        data={"actor": "sales", "source_kind": "partner_event", "source_id": "evt-1"},
    )

    assert response.status_code == 200
    assert "alliance-registration-push" in response.text
    assert "completed" in response.text
