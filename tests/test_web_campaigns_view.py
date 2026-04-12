import uuid

from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_campaigns_view_renders_campaign_information(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_campaign_rows",
        lambda db: [
            {
                "id": str(uuid.uuid4()),
                "name": "Spring Coaches Push",
                "slug": "spring-coaches-push",
                "status": "active",
                "objective": "Drive clinic registrations",
                "audience": "Travel ball coaches",
                "theme": "Proof over promises",
                "workflow_count": 2,
            }
        ],
    )

    response = client.get("/control-room/campaigns")

    assert response.status_code == 200
    assert "Campaigns" in response.text
    assert "Spring Coaches Push" in response.text
    assert "Drive clinic registrations" in response.text
    assert "Travel ball coaches" in response.text
    assert "Proof over promises" in response.text


def test_campaign_run_fragment_renders_results(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "run_campaign_from_web",
        lambda db, campaign_slug, actor="planner": {
            "campaign_slug": campaign_slug,
            "actor": actor,
            "workflow_runs": [
                {
                    "workflow_slug": "tuesday-linkedin-tl",
                    "workflow_name": "Tuesday LinkedIn TL",
                    "status": "completed",
                    "summary": "Generated one draft",
                }
            ],
        },
    )

    response = client.post(
        "/control-room/campaigns/spring-coaches-push/run",
        data={"actor": "ops"},
    )

    assert response.status_code == 200
    assert "spring-coaches-push" in response.text
    assert "Tuesday LinkedIn TL" in response.text
    assert "Generated one draft" in response.text
