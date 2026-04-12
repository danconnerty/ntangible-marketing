"""NTangible Marketing MCP Server — stdio transport.

Exposes 5 tools: health, workflows, drafts, manual_request, insights.
Connects to the hosted FastAPI app over HTTP using APP_BASE_URL / APP_API_KEY.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from ntangible_mcp.client import AppClient

logger = logging.getLogger("mcp.server")

mcp = FastMCP("ntangible-marketing")

_client: AppClient | None = None


def _get_client() -> AppClient:
    global _client
    if _client is None:
        _client = AppClient()
    return _client


def _fmt(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


# ── Tool 1: health ──────────────────────────────────────────────────────


@mcp.tool()
def health() -> str:
    """Check API reachability and auth. Returns system status including queue
    counts, or an error if the API is unreachable or the key is invalid."""
    return _fmt(_get_client().health_check())


# ── Tool 2: workflows ───────────────────────────────────────────────────


@mcp.tool()
def workflows(
    action: str,
    slug: str | None = None,
    name: str | None = None,
    platform: str | None = None,
    mode: str | None = None,
    description: str | None = None,
    timezone: str | None = None,
    content_type: str | None = None,
    feedback: str | None = None,
    version_number: int | None = None,
    actor: str | None = None,
    draft_id: str | None = None,
) -> str:
    """Manage marketing workflows.

    Actions:
      list              — List all workflows
      get               — Get workflow detail (requires slug)
      create            — Create a new workflow (requires name, slug, platform; optional mode, description, timezone, content_type)
      create_version    — Propose a new version from feedback (requires slug, feedback; optional actor, draft_id)
      activate_version  — Activate a specific version (requires slug, version_number)
      pause             — Pause a workflow (requires slug)
      resume            — Resume a paused workflow (requires slug)
    """
    client = _get_client()

    if action == "list":
        return _fmt(client.get("/api/mcp/workflows"))

    if action == "get":
        if not slug:
            return _fmt({"error": "slug is required for 'get'"})
        return _fmt(client.get(f"/api/control-room/workflows/{slug}"))

    if action == "create":
        if not all([name, slug, platform]):
            return _fmt({"error": "name, slug, and platform are required for 'create'"})
        body: dict[str, Any] = {"name": name, "slug": slug, "platform": platform}
        if mode:
            body["mode"] = mode
        if description:
            body["description"] = description
        if timezone:
            body["timezone"] = timezone
        if content_type:
            body["content_type"] = content_type
        return _fmt(client.post("/api/mcp/workflows", json=body))

    if action == "create_version":
        if not slug or not feedback:
            return _fmt({"error": "slug and feedback are required for 'create_version'"})
        body = {"feedback": feedback, "actor": actor or "mcp"}
        if draft_id:
            body["draft_id"] = draft_id
        return _fmt(client.post(f"/api/control-room/workflows/{slug}/improve", json=body))

    if action == "activate_version":
        if not slug or version_number is None:
            return _fmt({"error": "slug and version_number are required for 'activate_version'"})
        return _fmt(client.post(f"/api/control-room/workflows/{slug}/versions/{version_number}/activate"))

    if action == "pause":
        if not slug:
            return _fmt({"error": "slug is required for 'pause'"})
        # Need workflow_id — get it from detail
        detail = client.get(f"/api/mcp/workflows")
        wf = next((w for w in detail["workflows"] if w["slug"] == slug), None)
        if not wf:
            return _fmt({"error": f"Workflow '{slug}' not found"})
        return _fmt(client.post(f"/api/control-room/workflows/{wf['id']}/pause"))

    if action == "resume":
        if not slug:
            return _fmt({"error": "slug is required for 'resume'"})
        detail = client.get(f"/api/mcp/workflows")
        wf = next((w for w in detail["workflows"] if w["slug"] == slug), None)
        if not wf:
            return _fmt({"error": f"Workflow '{slug}' not found"})
        return _fmt(client.post(f"/api/control-room/workflows/{wf['id']}/resume"))

    return _fmt({"error": f"Unknown action '{action}'. Valid: list, get, create, create_version, activate_version, pause, resume"})


# ── Tool 3: drafts ──────────────────────────────────────────────────────


@mcp.tool()
def drafts(
    action: str,
    draft_id: str | None = None,
    queue: str | None = None,
    limit: int = 50,
    actor: str | None = None,
    notes: str | None = None,
    scheduled_at: str | None = None,
) -> str:
    """Manage draft content in the review queue.

    Actions:
      list_queue  — List drafts awaiting review (queue='manual' or 'automatic', default 'manual')
      get         — Get full draft detail with provenance (requires draft_id)
      approve     — Approve a draft for publishing (requires draft_id; optional scheduled_at ISO datetime, actor, notes)
      reject      — Reject a draft (requires draft_id; optional notes, actor)
    """
    client = _get_client()

    if action == "list_queue":
        q = queue or "manual"
        if q not in ("manual", "automatic"):
            return _fmt({"error": "queue must be 'manual' or 'automatic'"})
        return _fmt(client.get(f"/api/control-room/{q}", params={"limit": limit}))

    if action == "get":
        if not draft_id:
            return _fmt({"error": "draft_id is required for 'get'"})
        return _fmt(client.get(f"/api/control-room/drafts/{draft_id}"))

    if action == "approve":
        if not draft_id:
            return _fmt({"error": "draft_id is required for 'approve'"})
        body: dict[str, Any] = {
            "action": "schedule" if scheduled_at else "post_now",
            "actor": actor or "mcp",
        }
        if notes:
            body["notes"] = notes
        if scheduled_at:
            body["scheduled_at"] = scheduled_at
        return _fmt(client.post(f"/api/control-room/drafts/{draft_id}/action", json=body))

    if action == "reject":
        if not draft_id:
            return _fmt({"error": "draft_id is required for 'reject'"})
        body = {"action": "reject", "actor": actor or "mcp"}
        if notes:
            body["notes"] = notes
        return _fmt(client.post(f"/api/control-room/drafts/{draft_id}/action", json=body))

    return _fmt({"error": f"Unknown action '{action}'. Valid: list_queue, get, approve, reject"})


# ── Tool 4: manual_request ──────────────────────────────────────────────


@mcp.tool()
def manual_request(
    workflow_slug: str,
    request_text: str,
    actor: str = "mcp",
) -> str:
    """Create a manual content request for a workflow.

    Triggers the workflow engine to generate drafts from your request text.
    Returns the created trigger, job, and any generated drafts.

    Args:
      workflow_slug: The workflow to trigger (e.g. 'daily-x-post')
      request_text: What to write about (e.g. 'Write about our new product launch')
      actor: Who is making the request (default: 'mcp')
    """
    client = _get_client()
    return _fmt(client.post(
        f"/api/mcp/workflows/{workflow_slug}/manual-request",
        json={"request_text": request_text, "actor": actor},
    ))


# ── Tool 5: insights ────────────────────────────────────────────────────


@mcp.tool()
def insights(
    action: str,
    platform: str | None = None,
    workflow_slug: str | None = None,
    days: int = 30,
    query: str | None = None,
    limit: int = 50,
    history_type: str | None = None,
) -> str:
    """Query analytics, history, and the content brain.

    Actions:
      analytics_summary — Publishing analytics (optional platform, workflow_slug, days)
      search_history    — Search rejected/expired drafts (history_type='rejected' or 'expired', optional limit)
      search_brain      — Search the content brain knowledge base (optional query, platform, limit)
    """
    client = _get_client()

    if action == "analytics_summary":
        params: dict[str, Any] = {"days": days}
        if platform:
            params["platform"] = platform
        if workflow_slug:
            params["workflow_slug"] = workflow_slug
        return _fmt(client.get("/api/analytics/summary", params=params))

    if action == "search_history":
        ht = history_type or "rejected"
        if ht not in ("rejected", "expired"):
            return _fmt({"error": "history_type must be 'rejected' or 'expired'"})
        return _fmt(client.get(f"/api/control-room/history/{ht}", params={"limit": limit}))

    if action == "search_brain":
        params = {"limit": limit}
        if query:
            params["q"] = query
        if platform:
            params["platform"] = platform
        return _fmt(client.get("/content-brain/api/items", params=params))

    return _fmt({"error": f"Unknown action '{action}'. Valid: analytics_summary, search_history, search_brain"})


# ── Tool 6: process_file ────────────────────────────────────────────────


@mcp.tool()
def process_file(
    file_content: str,
    file_name: str,
    file_type: str | None = None,
) -> str:
    """Process a file through the ingestion pipeline.

    Sends the file content to the processing agent which will:
    - Extract knowledge (entities, relationships) into the brain graph
    - Check if any workflows should be triggered
    - Flag if the content warrants an alert

    Args:
        file_content: The text content of the file to process
        file_name: Original filename for context
        file_type: Optional MIME type hint (e.g. "application/pdf")
    """
    client = _get_client()
    body = {"content": file_content, "file_name": file_name}
    if file_type:
        body["file_type"] = file_type
    return _fmt(client.post("/api/mcp/process-file", json=body))


# ── Tool 7: get_context ──────────────────────────────────────────────────


@mcp.tool()
def get_context(
    query: str,
    topic: str | None = None,
    max_entities: int = 10,
    max_knowledge: int = 15,
) -> str:
    """Get brain context for a query. Searches the knowledge graph for relevant
    entities and knowledge nodes, returns structured context with relationships.

    Use this to understand what the brain knows about a topic, person, company,
    or any subject before taking action.

    Args:
        query: What to search for (e.g., "Alliance Sports partnership")
        topic: Optional topic filter (marketing, work, people, projects, finance)
        max_entities: Maximum entities to return (default 10)
        max_knowledge: Maximum knowledge nodes to return (default 15)
    """
    client = _get_client()
    params = {"q": query, "max_entities": max_entities, "max_knowledge": max_knowledge}
    if topic:
        params["topic"] = topic
    return _fmt(client.get("/api/mcp/context", params=params))


# ── Entry point ──────────────────────────────────────────────────────────


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
