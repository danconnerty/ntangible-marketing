import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.api.linkedin_routes as linkedin_routes
from app.database import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_linkedin_generate_requires_auth():
    response = client.post("/linkedin/generate", json={})
    assert response.status_code == 403


def test_linkedin_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/linkedin/generate" in paths
    assert "/linkedin/review" in paths


def test_linkedin_generate_returns_pipeline_result(monkeypatch):
    fake_post = SimpleNamespace(
        id=uuid.uuid4(),
        status=SimpleNamespace(value="needs_review"),
        approval_tier=SimpleNamespace(value="tier_2"),
        content="Pressure data beats vibes.",
        hashtags=["#MentalPerformance"],
        post_url=None,
    )

    def fake_get_db():
        yield object()

    def fake_generate(payload, db):
        assert payload["approval_tier"] == "tier_2"
        return fake_post

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(linkedin_routes, "generate_linkedin_item", fake_generate)
    response = client.post(
        "/linkedin/generate",
        headers={"Authorization": "Bearer test-secret-key"},
        json={
            "content_type": "thought_leadership",
            "pillar": "thought_leadership",
            "approval_tier": "tier_2",
            "claims": [],
            "context": "Pressure data beats vibes.",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_review"
    assert payload["approval_tier"] == "tier_2"
