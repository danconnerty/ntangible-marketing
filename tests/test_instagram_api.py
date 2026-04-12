import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.api.instagram_routes as instagram_routes
from app.database import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_instagram_generate_requires_auth():
    response = client.post("/instagram/generate", json={})
    assert response.status_code == 403


def test_instagram_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/instagram/generate" in paths
    assert "/instagram/review" in paths
    assert "/instagram/packages" in paths


def test_instagram_generate_returns_pipeline_result(monkeypatch):
    fake_result = {
        "draft": SimpleNamespace(
            id=uuid.uuid4(),
            state=SimpleNamespace(value="manual_ready"),
            content="Pressure is visible.\nAlliance events expose it quickly.\nComment if your staff wants cleaner signal.",
            hashtags=["#one", "#two", "#three", "#four", "#five", "#six"],
            platform_post_id=None,
            post_url=None,
            failure_reason=None,
            compliance_result={"approval_tier": "tier_2", "template_family": "partner_event_spotlight"},
        ),
        "assets": [SimpleNamespace(id=uuid.uuid4(), asset_role="slide_1", url="https://cdn.example.com/slide-1.png")],
        "package": SimpleNamespace(
            id=uuid.uuid4(),
            status=SimpleNamespace(value="needs_review"),
            partner_name="Alliance Fastpitch",
        ),
    }

    def fake_get_db():
        yield object()

    def fake_generate(payload, db):
        assert payload["approval_tier"] == "tier_2"
        return fake_result

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(instagram_routes, "generate_instagram_item", fake_generate)
    response = client.post(
        "/instagram/generate",
        headers={"Authorization": "Bearer test-secret-key"},
        json={
            "content_type": "partner_content",
            "pillar": "client_proof",
            "approval_tier": "tier_2",
            "partner_name": "Alliance Fastpitch",
            "claims": [],
            "context": "Alliance leaderboard update",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "manual_ready"
    assert payload["package"]["status"] == "needs_review"
    assert payload["assets"][0]["asset_role"] == "slide_1"
