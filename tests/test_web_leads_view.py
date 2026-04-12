import uuid

from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_leads_view_renders_accounts_and_tasks(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_lead_dashboard",
        lambda db: {
            "leads": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "West Coast Academy",
                    "stage": "qualified",
                    "priority": "high",
                    "next_touchpoint": "case-study-followup",
                    "open_task_count": 1,
                }
            ],
            "tasks": [
                {
                    "id": str(uuid.uuid4()),
                    "lead_name": "West Coast Academy",
                    "task_type": "case-study-followup",
                    "status": "open",
                    "summary": "Send proof-led follow-up with client evidence.",
                }
            ],
        },
    )

    response = client.get("/control-room/leads")

    assert response.status_code == 200
    assert "Leads" in response.text
    assert "West Coast Academy" in response.text
    assert "case-study-followup" in response.text
    assert "Send proof-led follow-up with client evidence." in response.text


def test_lead_generate_content_fragment_renders_result(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "generate_lead_content_from_web",
        lambda db, lead_id, platform="linkedin", actor="sales": {
            "workflow_slug": "lead-nurture-linkedin",
            "status": "manual_ready",
            "trigger_event_id": str(uuid.uuid4()),
            "platform": platform,
        },
    )

    response = client.post(
        f"/control-room/leads/{uuid.uuid4()}/generate-content",
        data={"platform": "linkedin", "actor": "sales"},
    )

    assert response.status_code == 200
    assert "lead-nurture-linkedin" in response.text
    assert "manual_ready" in response.text

