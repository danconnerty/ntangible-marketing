from fastapi.testclient import TestClient

import app.web.partner_portal as partner_portal
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_partner_portal_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/partner-portal/login" in paths
    assert "/partner-portal/submit" in paths
    assert "/partner-portal/packages" in paths


def test_partner_portal_login_sets_cookie(monkeypatch):
    monkeypatch.setattr(
        partner_portal,
        "authenticate_partner_portal_user",
        lambda db, username, password: {"slug": "alliance-fastpitch", "display_name": "Alliance Fastpitch"},
    )

    response = client.post(
        "/partner-portal/login",
        data={"username": "alliance", "password": "secret"},
        follow_redirects=False,
    )

    assert response.status_code in {302, 303, 307}
    assert "partner_portal_session" in response.cookies or "set-cookie" in response.headers


def test_partner_portal_submit_renders_submission_result(monkeypatch):
    client.post(
        "/partner-portal/login",
        data={"username": "alliance", "password": "secret"},
        follow_redirects=False,
    )
    monkeypatch.setattr(
        partner_portal,
        "submit_partner_portal_event",
        lambda db, partner_slug, payload: {
            "partner_slug": partner_slug,
            "results": [{"workflow_slug": "partner-alliance-assessment-x", "status": "manual_ready"}],
        },
    )

    response = client.post(
        "/partner-portal/submit",
        data={"partner_slug": "alliance-fastpitch", "event_type": "assessment_completed", "external_event_id": "evt-1"},
    )

    assert response.status_code == 200
    assert "partner-alliance-assessment-x" in response.text
