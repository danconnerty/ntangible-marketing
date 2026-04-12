import uuid

from fastapi.testclient import TestClient

import app.api.campaign_routes as campaign_routes
from app.database import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_campaign_routes_are_registered():
    paths = {route.path for route in app.routes}

    assert "/api/control-room/campaigns" in paths
    assert "/api/control-room/campaigns/{campaign_slug}/run" in paths


def test_list_campaigns_api_returns_campaigns(monkeypatch):
    class FakeDB:
        pass

    def fake_get_db():
        yield FakeDB()

    class FakeCampaignService:
        def __init__(self, db):
            self.db = db

        def list_campaigns(self):
            return [
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
            ]

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(campaign_routes, "CampaignService", FakeCampaignService)
    response = client.get(
        "/api/control-room/campaigns",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["campaigns"][0]["slug"] == "spring-coaches-push"


def test_run_campaign_api_returns_summary(monkeypatch):
    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeCampaignService:
        def __init__(self, db):
            self.db = db

        def run_campaign_by_slug(self, campaign_slug, actor="planner"):
            assert campaign_slug == "spring-coaches-push"
            assert actor == "ops"
            return {
                "campaign_slug": campaign_slug,
                "actor": actor,
                "workflow_runs": [
                    {
                        "workflow_slug": "tuesday-linkedin-tl",
                        "status": "completed",
                        "summary": "Generated one draft",
                    }
                ],
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(campaign_routes, "CampaignService", FakeCampaignService)
    response = client.post(
        "/api/control-room/campaigns/spring-coaches-push/run",
        headers={"Authorization": "Bearer test-secret-key"},
        json={"actor": "ops"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["campaign_slug"] == "spring-coaches-push"
    assert payload["workflow_runs"][0]["workflow_slug"] == "tuesday-linkedin-tl"
    assert payload["workflow_runs"][0]["status"] == "completed"
