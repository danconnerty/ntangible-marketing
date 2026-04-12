import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.sports_routes as sports_routes
from app.database import get_db


def _client():
    app = FastAPI()
    app.include_router(sports_routes.router)
    return TestClient(app, raise_server_exceptions=False), app


def test_sports_routes_are_registered():
    paths = {route.path for route in sports_routes.router.routes}
    assert "/api/control-room/sports" in paths
    assert "/api/control-room/sports/calendar" in paths
    assert "/api/control-room/sports/windows/{window_slug}/stage" in paths


def test_list_sports_calendar_returns_calendar_days_and_events(monkeypatch):
    client, app = _client()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self, days=28):
            return {
                "windows": [],
                "calendar_days": [{"date": "2026-04-01", "label": "Apr 01", "weekday": "Wed", "is_today": True, "windows": []}],
                "stage_runs": [],
            }

        def list_calendar_window(self, days=28):
            return [
                {
                    "event_name": "Signing Day Window",
                    "start_at": "2026-04-01",
                    "end_at": "2026-04-30",
                    "sport": "multi-sport",
                    "event_type": "signing_day",
                }
            ]

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(sports_routes, "SportsCalendarService", FakeService)

    response = client.get(
        "/api/control-room/sports/calendar",
        headers={"Authorization": "Bearer test-secret-key"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["days"] == 28
    assert payload["calendar_days"][0]["label"] == "Apr 01"
    assert payload["events"][0]["event_name"] == "Signing Day Window"


def test_stage_sports_window_returns_html_fragment(monkeypatch):
    client, app = _client()

    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeService:
        def __init__(self, db):
            self.db = db

        def list_dashboard(self, days=28):
            return {"windows": [], "calendar_days": [], "stage_runs": []}

        def list_calendar_window(self, days=28):
            return []

        def stage_window(self, window_slug, actor="planner", platforms=None, note=None):
            assert window_slug == "womens-summer-signing-window"
            assert actor == "coach"
            assert platforms == ["linkedin"]
            return {
                "window_title": "Signing Day Window",
                "actor": actor,
                "runs": [
                    {
                        "workflow_name": "Signing Day LinkedIn",
                        "workflow_slug": "sports-womens-summer-signing-window-linkedin",
                        "platform": "linkedin",
                        "status": "manual_ready",
                        "content": "LinkedIn draft body",
                    }
                ],
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(sports_routes, "SportsCalendarService", FakeService)

    response = client.post(
        "/api/control-room/sports/windows/womens-summer-signing-window/stage",
        headers={
            "Authorization": "Bearer test-secret-key",
            "HX-Request": "true",
        },
        data={"actor": "coach", "platforms": "linkedin", "note": "Lead with proof."},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Sports Stage" in response.text
    assert "Signing Day LinkedIn" in response.text
    assert "manual_ready" in response.text
