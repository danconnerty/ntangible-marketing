from fastapi.testclient import TestClient
from pathlib import Path

import app.api.workflow_routes as workflow_routes
import app.web.routes as web_routes
from app.database import get_db
from app.main import app


client = TestClient(app, raise_server_exceptions=False)


def test_workflow_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/control-room/workflows/{workflow_slug}" in paths
    assert "/api/control-room/workflows/{workflow_slug}/improve" in paths
    assert "/api/control-room/workflows/{workflow_slug}/versions/{version_number}/activate" in paths
    assert "/control-room/workflows/{workflow_slug}" in paths


def test_improve_workflow_api_returns_proposal(monkeypatch):
    class FakeDB:
        def commit(self):
            return None

    def fake_get_db():
        yield FakeDB()

    class FakeEditor:
        def __init__(self, db):
            self.db = db

        def propose_version(self, workflow_slug, feedback, actor="claude", draft_id=None):
            assert workflow_slug == "tuesday-linkedin-tl"
            assert "corporate" in feedback
            return {
                "workflow": {"name": "Tuesday LinkedIn TL", "slug": workflow_slug, "platform": "linkedin"},
                "current_version": 1,
                "proposed_version": 2,
                "changes": ["prompt.tone_notes: '' -> 'Not corporate'"],
                "approved_examples": [],
                "rejected_examples": [],
            }

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr(workflow_routes, "WorkflowEditor", FakeEditor)
    response = client.post(
        "/api/control-room/workflows/tuesday-linkedin-tl/improve",
        headers={"Authorization": "Bearer test-secret-key"},
        json={"feedback": "too corporate", "actor": "boss"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["proposed_version"] == 2
    assert payload["changes"][0].startswith("prompt.tone_notes")


def test_improve_workflow_fragment_returns_html(monkeypatch):
    monkeypatch.setattr(
        web_routes,
        "WorkflowEditor",
        lambda db: type(
            "FakeEditor",
            (),
            {
                "propose_version": lambda self, workflow_slug, feedback, actor="admin", draft_id=None: {
                    "workflow": {"name": "Tuesday LinkedIn TL", "slug": workflow_slug, "platform": "linkedin"},
                    "current_version": 1,
                    "proposed_version": 2,
                    "changes": ["prompt.tone_notes: '' -> 'Not corporate'"],
                    "approved_examples": [],
                    "rejected_examples": [],
                }
            },
        )(),
    )

    response = client.post(
        "/control-room/workflows/tuesday-linkedin-tl/improve",
        data={"feedback": "too corporate", "actor": "boss"},
    )

    assert response.status_code == 200
    assert "Workflow Proposal" in response.text
    assert "v1" in response.text
    assert "v2" in response.text


def test_workflow_create_missing_fields_redirects_back_to_control_room():
    response = client.post("/control-room/workflows/create", data={"name": "", "slug": ""}, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/control-room/workflows?error=")


def test_workflow_wizard_preserves_computed_alpine_getters():
    repo_root = Path(__file__).resolve().parents[1]

    for template_name in ("workflows.html", "platform_detail.html"):
        template = (repo_root / "app" / "web" / "templates" / template_name).read_text()
        assert 'x-data="{ ...workflowWizard() }"' not in template
        assert 'x-data="workflowWizard()"' in template
