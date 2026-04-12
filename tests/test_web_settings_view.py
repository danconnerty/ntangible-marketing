from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


def test_settings_view_renders_control_panels(monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)
    monkeypatch.setattr(
        web_routes,
        "load_settings_summary",
        lambda db=None: {
            "timezone": "America/Toronto",
            "auth_required": True,
            "scheduler_status": {"paused_workflows": 2, "unhealthy_workflows": 1, "upcoming_24h": 4},
            "publishers": {
                "x": "mock",
                "linkedin": "mock",
                "instagram": "mock",
                "newsletter": "mock",
            },
        },
    )

    response = client.get("/control-room/settings")

    assert response.status_code == 200
    assert "Control Room Settings" in response.text
    assert "America/Toronto" in response.text
    assert "Session login required" in response.text
    assert "Pause All Automatic Workflows" in response.text


def test_settings_view_renders_connected_accounts(monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)
    monkeypatch.setattr(
        web_routes,
        "load_settings_summary",
        lambda db=None: {
            "timezone": "America/Toronto",
            "auth_required": True,
            "scheduler_status": {"paused_workflows": 2, "unhealthy_workflows": 1, "upcoming_24h": 4},
            "publishers": {
                "x": "mock",
                "linkedin": "mock",
                "instagram": "mock",
                "newsletter": "mock",
            },
            "connections": [
                {
                    "id": "conn-1",
                    "channel": "linkedin",
                    "provider_key": "linkedin",
                    "status": "connected",
                    "connection_label": "NTangible LinkedIn",
                    "active_destination_label": "NTangible Main Page",
                    "destinations": [
                        {"id": "dest-1", "label": "NTangible Main Page", "is_active": True},
                        {"id": "dest-2", "label": "Regional Page", "is_active": False},
                    ],
                }
            ],
        },
    )

    response = client.get("/control-room/settings")

    assert response.status_code == 200
    assert "Connected Accounts" in response.text
    assert "NTangible LinkedIn" in response.text
    assert "NTangible Main Page" in response.text
    assert "Regional Page" in response.text
    assert "/control-room/settings/destinations/dest-2/activate" in response.text
    assert "/control-room/settings/destinations/dest-1/delete" in response.text


def test_settings_connection_action_saves_connection(monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)
    captured = {}

    class FakeService:
        def __init__(self, db):
            captured["db"] = db

        def upsert_connection(self, **kwargs):
            captured["upsert"] = kwargs
            return object()

    monkeypatch.setattr(web_routes, "PublishingConnectionService", FakeService, raising=False)

    response = client.post(
        "/control-room/settings/connections",
        data={
            "channel": "linkedin",
            "provider_key": "linkedin",
            "auth_mode": "oauth",
            "connection_label": "NTangible LinkedIn",
            "status": "connected",
            "config_json": "{\"api_version\":\"202504\"}",
            "credential_json": "{\"access_token\":\"token\"}",
        },
    )

    assert response.status_code == 200
    assert captured["upsert"]["channel"] == "linkedin"
    assert captured["upsert"]["provider_key"] == "linkedin"
    assert captured["upsert"]["credential_json"] == {"access_token": "token"}


def test_settings_destination_action_adds_destination(monkeypatch):
    client = TestClient(app, raise_server_exceptions=False)
    captured = {}

    class FakeService:
        def __init__(self, db):
            captured["db"] = db

        def add_destination(self, **kwargs):
            captured["add_destination"] = kwargs
            return object()

    monkeypatch.setattr(web_routes, "PublishingConnectionService", FakeService, raising=False)

    response = client.post(
        "/control-room/settings/destinations",
        data={
            "channel": "linkedin",
            "external_id": "urn:li:organization:123",
            "destination_type": "organization",
            "label": "NTangible Main Page",
            "config_json": "{\"organization_urn\":\"urn:li:organization:123\"}",
            "activate": "true",
        },
    )

    assert response.status_code == 200
    assert captured["add_destination"]["channel"] == "linkedin"
    assert captured["add_destination"]["external_id"] == "urn:li:organization:123"
    assert captured["add_destination"]["activate"] is True


def test_control_room_requires_login_when_enabled(monkeypatch):
    monkeypatch.setenv("CONTROL_ROOM_REQUIRE_AUTH", "true")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/control-room/manual", follow_redirects=False)

    assert response.status_code in {302, 303, 307}


def test_control_room_login_redirects_to_cognito(monkeypatch):
    monkeypatch.setenv("CONTROL_ROOM_REQUIRE_AUTH", "true")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/control-room/login", follow_redirects=False)

    assert response.status_code in {302, 303, 307}
    assert "amazoncognito.com" in response.headers.get("location", "")
