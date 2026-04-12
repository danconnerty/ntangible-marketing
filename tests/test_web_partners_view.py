import uuid

from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_partners_view_renders_events_and_bundles(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_partner_dashboard",
        lambda db: {
            "partners": [{"slug": "alliance-fastpitch", "display_name": "Alliance Fastpitch"}],
            "events": [{"event_type": "assessment_completed", "partner_name": "Alliance Fastpitch"}],
            "bundles": [{"platform": "instagram", "partner_name": "Alliance Fastpitch"}],
        },
    )

    response = client.get("/control-room/partners")

    assert response.status_code == 200
    assert "Alliance Fastpitch" in response.text


def test_partner_event_fragment_renders_result(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "ingest_partner_event_from_web",
        lambda db, partner_slug, payload: {
            "partner_slug": partner_slug,
            "results": [{"workflow_slug": "partner-alliance-assessment-x", "status": "manual_ready"}],
        },
    )

    response = client.post(
        "/control-room/partners/alliance_fastpitch/events",
        data={"event_type": "assessment_completed", "external_event_id": "evt-1"},
    )

    assert response.status_code == 200
    assert "partner-alliance-assessment-x" in response.text


def test_partner_bundle_fragment_renders_result(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "update_partner_bundle_from_web",
        lambda db, bundle_id, status="delivered": {
            "bundle_id": str(bundle_id),
            "status": status,
            "message": "Bundle marked delivered.",
        },
    )

    response = client.post(
        f"/control-room/partners/bundles/{uuid.uuid4()}/action",
        data={"status": "delivered"},
    )

    assert response.status_code == 200
    assert "Bundle marked delivered." in response.text
