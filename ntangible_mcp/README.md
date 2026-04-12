# NTangible Marketing MCP Server

A local stdio MCP server that operates the hosted NTangible Marketing app over HTTP.

## Setup

```bash
# Install the mcp package (in the project venv)
uv pip install mcp

# Set environment variables
export APP_BASE_URL=https://your-app.example.com   # or http://3.21.155.208
export APP_API_KEY=your-api-key
```

## Run

```bash
python -m ntangible_mcp.server
```

Or configure in Claude Code's `~/.claude.json`:

```json
{
  "mcpServers": {
    "ntangible": {
      "command": "python",
      "args": ["-m", "ntangible_mcp.server"],
      "cwd": "/path/to/ntangible_marketing",
      "env": {
        "APP_BASE_URL": "http://3.21.155.208",
        "APP_API_KEY": "your-key"
      }
    }
  }
}
```

## Tools

### 1. `health`
Check API reachability and auth. No arguments.

### 2. `workflows`
Manage marketing workflows.

| Action | Required Args | Optional Args |
|--------|--------------|---------------|
| `list` | — | — |
| `get` | `slug` | — |
| `create` | `name`, `slug`, `platform` | `mode`, `description`, `timezone`, `content_type` |
| `create_version` | `slug`, `feedback` | `actor`, `draft_id` |
| `activate_version` | `slug`, `version_number` | — |
| `pause` | `slug` | — |
| `resume` | `slug` | — |

Platforms: `x`, `linkedin`, `instagram`, `newsletter`, `blog`
Modes: `manual`, `automatic`

### 3. `drafts`
Manage the draft review queue.

| Action | Required Args | Optional Args |
|--------|--------------|---------------|
| `list_queue` | — | `queue` (manual/automatic), `limit` |
| `get` | `draft_id` | — |
| `approve` | `draft_id` | `scheduled_at` (ISO datetime), `actor`, `notes` |
| `reject` | `draft_id` | `notes`, `actor` |

### 4. `manual_request`
Trigger content generation for a workflow.

| Arg | Required | Description |
|-----|----------|-------------|
| `workflow_slug` | yes | Which workflow to trigger |
| `request_text` | yes | What to write about |
| `actor` | no | Who is requesting (default: `mcp`) |

### 5. `insights`
Query analytics, history, and the content brain.

| Action | Optional Args |
|--------|---------------|
| `analytics_summary` | `platform`, `workflow_slug`, `days` |
| `search_history` | `history_type` (rejected/expired), `limit` |
| `search_brain` | `query`, `platform`, `limit` |

### 6. `process_file`
Send a file through the processing agent for knowledge extraction.

The file content is queued, then the hosted processor classifies it (knowledge kind, topic, confidence), extracts entities, and reasons about connections to the existing graph.

| Arg | Required | Description |
|-----|----------|-------------|
| `file_content` | yes | The text content to process |
| `file_name` | yes | Original filename for context |
| `file_type` | no | MIME type hint (e.g. `application/pdf`) |

### 7. `get_context`
Query the knowledge graph to assemble a context packet for a task.

Searches entities by name, expands their edges, finds related knowledge nodes, and returns structured context. Use this before taking action on a topic, person, or company.

| Arg | Required | Description |
|-----|----------|-------------|
| `query` | yes | What to search for (e.g. "Alliance Sports partnership") |
| `topic` | no | Filter by topic key (marketing, work, people, projects, finance) |
| `max_entities` | no | Max entities to return (default 10) |
| `max_knowledge` | no | Max knowledge nodes to return (default 15) |

## New API Endpoints

The MCP server relies on three new endpoints added at `/api/mcp/`:

- `GET /api/mcp/workflows` — List all workflows
- `POST /api/mcp/workflows` — Create a workflow
- `POST /api/mcp/workflows/{slug}/manual-request` — Fire a manual request

All other calls use existing control-room and analytics endpoints.

## Tests

```bash
pytest tests/test_mcp_server.py -v    # 26 unit tests (no DB needed)
pytest tests/test_mcp_routes.py -v    # API route tests (needs local Postgres)
```
