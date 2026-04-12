import uuid

from fastapi.testclient import TestClient

import app.web.routes as web_routes
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def _sample_card(**overrides):
    card = {
        "id": str(uuid.uuid4()),
        "platform": "linkedin",
        "content": "Pressure data beats vibes when coaches can trust the signal.",
        "hashtags": ["#MentalPerformance", "#Recruiting"],
        "created_label": "Apr 06, 09:00",
        "recommended_label": "14:00",
        "workflow_name": "Tuesday LinkedIn TL",
        "workflow_slug": "tuesday-linkedin-tl",
        "version_number": 2,
        "trigger_label": "Calendar Trigger",
        "trigger_class": "trigger-calendar",
        "trigger_reason": "Generated from Tuesday recurring calendar rule",
        "state": "manual_ready",
        "notes": "Tone is too corporate.",
        "expires_label": "Apr 06, 23:59",
    }
    card.update(overrides)
    return card


def test_manual_view_renders_provenance_and_actions(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_manual_cards",
        lambda db, limit=50: [_sample_card()],
    )

    response = client.get("/control-room/manual")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Manual Queue" in response.text
    assert "Tuesday LinkedIn TL" in response.text
    assert "Calendar Trigger" in response.text
    assert "Generated from Tuesday recurring calendar rule" in response.text
    assert "Post Now" in response.text
    assert "Schedule" in response.text
    assert "Reject" in response.text
    assert "Why This Draft?" in response.text
    assert "Improve Workflow" in response.text


def test_draft_panel_renders_provenance_and_compliance(monkeypatch):
    draft_id = str(uuid.uuid4())
    monkeypatch.setattr(
        web_routes,
        "load_draft_panel",
        lambda db, incoming_draft_id, focus="why": {
            "id": draft_id,
            "content": "Pressure data beats vibes.",
            "workflow_name": "Tuesday LinkedIn TL",
            "workflow_slug": "tuesday-linkedin-tl",
            "version_number": 3,
            "trigger_label": "Calendar Trigger",
            "trigger_reason": "Generated from Tuesday recurring calendar rule",
            "compliance_result": {"passed": True, "checks_run": ["char_limit", "claims"]},
            "prompt_snapshot": {"system": "sys", "user": "usr"},
            "asset_items": [],
            "focus": "why",
        },
    )

    response = client.get(f"/control-room/drafts/{draft_id}/panel")

    assert response.status_code == 200
    assert "Why This Draft?" in response.text
    assert "Tuesday LinkedIn TL" in response.text
    assert "Calendar Trigger" in response.text
    assert "Generated from Tuesday recurring calendar rule" in response.text
    assert "char_limit" in response.text


def test_rejected_view_shows_notes_and_workflow_context(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_history_cards",
        lambda db, state, limit=50: [_sample_card()],
    )

    response = client.get("/control-room/rejected")

    assert response.status_code == 200
    assert "Read-only history of rejected drafts" in response.text
    assert "Tuesday LinkedIn TL" in response.text
    assert "Tone is too corporate." in response.text
    assert "Calendar Trigger" in response.text


def test_expired_view_shows_expiry_and_workflow_context(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_history_cards",
        lambda db, state, limit=50: [_sample_card()],
    )

    response = client.get("/control-room/expired")

    assert response.status_code == 200
    assert "Read-only history of drafts that timed out" in response.text
    assert "Tuesday LinkedIn TL" in response.text
    assert "Apr 06, 23:59" in response.text
    assert "Calendar Trigger" in response.text


def test_web_action_route_returns_html_fragment(monkeypatch):
    draft_id = str(uuid.uuid4())
    monkeypatch.setattr(
        web_routes,
        "apply_web_action",
        lambda db, incoming_draft_id, action, actor, notes=None, scheduled_at_raw=None: {
            "id": draft_id,
            "status_label": "Rejected",
            "status_class": "badge-danger",
            "message": "Draft moved to rejected history.",
        },
    )

    response = client.post(
        f"/control-room/drafts/{draft_id}/action",
        data={"action": "reject", "actor": "boss"},
    )

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Draft moved to rejected history." in response.text


def test_manual_view_renders_newsletter_subject_preview_and_segment(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "load_manual_cards",
        lambda db, limit=50: [
            _sample_card(
                platform="newsletter",
                workflow_name="Monthly Newsletter",
                workflow_slug="monthly-newsletter",
                content="Full newsletter body for operator review.",
                hashtags=[],
                newsletter_subject="April pressure data coaches should use",
                newsletter_preview_text="What the latest dataset changed.",
                newsletter_segment="coaches_front_offices",
            )
        ],
    )

    response = client.get("/control-room/manual")

    assert response.status_code == 200
    assert "Monthly Newsletter" in response.text
    assert "April pressure data coaches should use" in response.text
    assert "What the latest dataset changed." in response.text
    assert "coaches_front_offices" in response.text
