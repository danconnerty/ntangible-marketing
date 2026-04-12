import uuid

from fastapi.testclient import TestClient

import app.api.analytics_routes as analytics_routes
from app.database import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_analytics_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/analytics/summary" in paths
    assert "/api/analytics/publications/{publication_id}" in paths
    assert "/api/analytics/recycle-candidates" in paths


def test_analytics_summary_endpoint_returns_rollups(monkeypatch):
    def fake_get_db():
        yield object()

    def fake_summary(db, platform=None, workflow_slug=None, days=30):
        assert platform == "linkedin"
        assert workflow_slug == "tuesday-linkedin-tl"
        assert days == 14
        return {
            "summary": {"promotion_confidence": 0.78, "publication_success_rate": 0.8},
            "workflow_metrics": [{"workflow_slug": "tuesday-linkedin-tl", "promotion_confidence": 0.78}],
            "platform_metrics": [{"platform": "linkedin", "promotion_confidence": 0.78}],
            "filters": {"platform": platform, "workflow_slug": workflow_slug, "days": days},
        }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(analytics_routes, "build_analytics_summary", fake_summary)
    response = client.get(
        "/api/analytics/summary?platform=linkedin&workflow_slug=tuesday-linkedin-tl&days=14",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["promotion_confidence"] == 0.78
    assert payload["workflow_metrics"][0]["workflow_slug"] == "tuesday-linkedin-tl"


def test_analytics_publication_detail_endpoint_returns_snapshots(monkeypatch):
    publication_id = uuid.uuid4()

    def fake_get_db():
        yield object()

    def fake_detail(db, incoming_publication_id):
        assert incoming_publication_id == publication_id
        return {
            "publication": {"id": str(publication_id), "platform": "x"},
            "snapshots": [{"metrics": {"impressions": 1200, "engagement_rate": 0.07}}],
        }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(analytics_routes, "get_publication_analytics_detail", fake_detail)
    response = client.get(
        f"/api/analytics/publications/{publication_id}",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["snapshots"][0]["metrics"]["impressions"] == 1200


def test_analytics_recycle_candidates_endpoint_returns_items(monkeypatch):
    def fake_get_db():
        yield object()

    def fake_candidates(db, platform=None, days=90, limit=25):
        assert platform == "linkedin"
        assert days == 60
        assert limit == 5
        return [
            {
                "publication_id": str(uuid.uuid4()),
                "workflow_name": "Tuesday LinkedIn TL",
                "content_score": 82.4,
                "recycle_recommended": True,
            }
        ]

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(analytics_routes, "list_recycle_candidates", fake_candidates)
    response = client.get(
        "/api/analytics/recycle-candidates?platform=linkedin&days=60&limit=5",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["content_score"] == 82.4
