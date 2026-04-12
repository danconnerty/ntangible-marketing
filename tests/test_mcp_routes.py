"""Tests for app/api/mcp_routes.py — the thin API endpoints for MCP."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    from app.config import get_settings
    key = get_settings().api_key
    return {"Authorization": f"Bearer {key}"}


def test_list_workflows_requires_auth(client):
    resp = client.get("/api/mcp/workflows")
    assert resp.status_code in (401, 403)


def test_list_workflows(client, auth_headers):
    resp = client.get("/api/mcp/workflows", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "workflows" in data
    assert "count" in data


def test_create_workflow_bad_platform(client, auth_headers):
    resp = client.post(
        "/api/mcp/workflows",
        headers=auth_headers,
        json={"name": "Test", "slug": f"test-{uuid.uuid4().hex[:8]}", "platform": "tiktok"},
    )
    assert resp.status_code == 400
    assert "Invalid platform" in resp.json()["detail"]


def test_create_workflow_duplicate_slug(client, auth_headers):
    slug = f"dup-{uuid.uuid4().hex[:8]}"
    resp1 = client.post(
        "/api/mcp/workflows",
        headers=auth_headers,
        json={"name": "Test", "slug": slug, "platform": "x"},
    )
    if resp1.status_code == 200:
        resp2 = client.post(
            "/api/mcp/workflows",
            headers=auth_headers,
            json={"name": "Test 2", "slug": slug, "platform": "x"},
        )
        assert resp2.status_code == 409


def test_manual_request_404(client, auth_headers):
    resp = client.post(
        "/api/mcp/workflows/nonexistent-workflow/manual-request",
        headers=auth_headers,
        json={"request_text": "test"},
    )
    assert resp.status_code == 404
