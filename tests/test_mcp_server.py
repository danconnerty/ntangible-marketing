"""Tests for the MCP server tools and the thin API endpoints they call."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ntangible_mcp.client import AppClient
from ntangible_mcp.server import (
    _get_client,
    drafts,
    health,
    insights,
    manual_request,
    workflows,
)


# ── Client tests ─────────────────────────────────────────────────────────


def test_client_requires_base_url():
    with pytest.raises(ValueError, match="APP_BASE_URL"):
        AppClient(base_url="", api_key="test")


def test_client_requires_api_key():
    with pytest.raises(ValueError, match="APP_API_KEY"):
        AppClient(base_url="http://localhost", api_key="")


# ── Helpers ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_client():
    """Replace the global client with a mock for every test."""
    import ntangible_mcp.server as mod

    client = MagicMock(spec=AppClient)
    mod._client = client
    yield client
    mod._client = None


def _parse(result: str) -> dict:
    return json.loads(result)


# ── health ───────────────────────────────────────────────────────────────


def test_health_ok(mock_client):
    mock_client.health_check.return_value = {"status": "ok", "data": {"drafts": 3}}
    result = _parse(health())
    assert result["status"] == "ok"


# ── workflows ────────────────────────────────────────────────────────────


def test_workflows_list(mock_client):
    mock_client.get.return_value = {"workflows": [], "count": 0}
    result = _parse(workflows(action="list"))
    assert result["count"] == 0
    mock_client.get.assert_called_once_with("/api/mcp/workflows")


def test_workflows_get(mock_client):
    mock_client.get.return_value = {"workflow": {"slug": "daily-x"}}
    result = _parse(workflows(action="get", slug="daily-x"))
    assert result["workflow"]["slug"] == "daily-x"


def test_workflows_get_missing_slug(mock_client):
    result = _parse(workflows(action="get"))
    assert "error" in result


def test_workflows_create(mock_client):
    mock_client.post.return_value = {"id": "abc", "slug": "test"}
    result = _parse(workflows(action="create", name="Test", slug="test", platform="x"))
    assert result["slug"] == "test"
    mock_client.post.assert_called_once()


def test_workflows_create_missing_fields(mock_client):
    result = _parse(workflows(action="create", name="Test"))
    assert "error" in result


def test_workflows_pause(mock_client):
    mock_client.get.return_value = {"workflows": [{"slug": "daily-x", "id": "abc"}]}
    mock_client.post.return_value = {"workflow_id": "abc", "paused_at": "2024-01-01"}
    result = _parse(workflows(action="pause", slug="daily-x"))
    assert "paused_at" in result


def test_workflows_resume(mock_client):
    mock_client.get.return_value = {"workflows": [{"slug": "daily-x", "id": "abc"}]}
    mock_client.post.return_value = {"workflow_id": "abc", "paused_at": None}
    _parse(workflows(action="resume", slug="daily-x"))


def test_workflows_activate_version(mock_client):
    mock_client.post.return_value = {"workflow_slug": "daily-x", "active_version": 2}
    result = _parse(workflows(action="activate_version", slug="daily-x", version_number=2))
    assert result["active_version"] == 2


def test_workflows_create_version(mock_client):
    mock_client.post.return_value = {"version_number": 3}
    result = _parse(workflows(action="create_version", slug="daily-x", feedback="more emoji"))
    assert result["version_number"] == 3


def test_workflows_unknown_action(mock_client):
    result = _parse(workflows(action="explode"))
    assert "error" in result


# ── drafts ───────────────────────────────────────────────────────────────


def test_drafts_list_queue(mock_client):
    mock_client.get.return_value = {"drafts": [], "count": 0}
    result = _parse(drafts(action="list_queue"))
    assert result["count"] == 0
    mock_client.get.assert_called_once_with("/api/control-room/manual", params={"limit": 50})


def test_drafts_list_queue_automatic(mock_client):
    mock_client.get.return_value = {"drafts": [], "count": 0}
    drafts(action="list_queue", queue="automatic")
    mock_client.get.assert_called_once_with("/api/control-room/automatic", params={"limit": 50})


def test_drafts_get(mock_client):
    mock_client.get.return_value = {"id": "abc", "state": "manual_ready"}
    result = _parse(drafts(action="get", draft_id="abc"))
    assert result["id"] == "abc"


def test_drafts_approve(mock_client):
    mock_client.post.return_value = {"id": "abc", "state": "publishing"}
    result = _parse(drafts(action="approve", draft_id="abc"))
    assert result["state"] == "publishing"
    call_body = mock_client.post.call_args[1]["json"]
    assert call_body["action"] == "post_now"


def test_drafts_approve_scheduled(mock_client):
    mock_client.post.return_value = {"id": "abc", "state": "scheduled"}
    drafts(action="approve", draft_id="abc", scheduled_at="2024-06-01T12:00:00Z")
    call_body = mock_client.post.call_args[1]["json"]
    assert call_body["action"] == "schedule"
    assert call_body["scheduled_at"] == "2024-06-01T12:00:00Z"


def test_drafts_reject(mock_client):
    mock_client.post.return_value = {"id": "abc", "state": "rejected"}
    result = _parse(drafts(action="reject", draft_id="abc", notes="off-brand"))
    assert result["state"] == "rejected"


def test_drafts_missing_id(mock_client):
    result = _parse(drafts(action="get"))
    assert "error" in result


def test_drafts_unknown_action(mock_client):
    result = _parse(drafts(action="nope"))
    assert "error" in result


# ── manual_request ───────────────────────────────────────────────────────


def test_manual_request_ok(mock_client):
    mock_client.post.return_value = {
        "trigger_id": "t1",
        "job_id": "j1",
        "job_status": "completed",
        "drafts": [{"id": "d1", "state": "manual_ready"}],
    }
    result = _parse(manual_request(workflow_slug="daily-x", request_text="Write about AI"))
    assert result["job_status"] == "completed"
    assert len(result["drafts"]) == 1


# ── insights ─────────────────────────────────────────────────────────────


def test_insights_analytics_summary(mock_client):
    mock_client.get.return_value = {"total_published": 42}
    result = _parse(insights(action="analytics_summary", days=7))
    assert result["total_published"] == 42
    mock_client.get.assert_called_once_with("/api/analytics/summary", params={"days": 7})


def test_insights_search_history(mock_client):
    mock_client.get.return_value = {"items": [], "count": 0}
    insights(action="search_history", history_type="expired", limit=10)
    mock_client.get.assert_called_once_with("/api/control-room/history/expired", params={"limit": 10})


def test_insights_search_brain(mock_client):
    mock_client.get.return_value = {"items": [], "query": "AI"}
    insights(action="search_brain", query="AI", platform="x")
    mock_client.get.assert_called_once_with(
        "/content-brain/api/items", params={"limit": 50, "q": "AI", "platform": "x"}
    )


def test_insights_unknown_action(mock_client):
    result = _parse(insights(action="nope"))
    assert "error" in result
