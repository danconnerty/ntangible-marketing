# NTangible Marketing Engine

## Quick Start (MCP with Claude Code)

The fastest way to interact with the marketing engine is through the MCP server in Claude Code. It connects to the hosted production API — no local server or database required.

### 1. Clone and install

```bash
git clone <repo-url>
cd ntangible_marketing
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Set the API key

Add this to your shell profile (`~/.zshrc` or `~/.bashrc`) so it persists:

```bash
export APP_API_KEY=<ask Elliot for the production API key>
```

Then reload: `source ~/.zshrc`

### 3. Open in Claude Code

Open the project folder in Claude Code. The `.mcp.json` is already configured — the MCP tools will be available automatically.

### What you can do

Ask Claude things like:

- "What workflows do we have?"
- "Create a draft for the LinkedIn Company Update workflow about our new product launch"
- "Show me the analytics summary for the last 7 days"
- "What's in the draft review queue?"
- "Process this file through the brain" (attach or paste content)

### MCP Tools

| Tool | Description |
|------|-------------|
| `health` | Check API status |
| `workflows` | List, create, pause, resume workflows |
| `drafts` | Review queue — list, approve, reject drafts |
| `manual_request` | Trigger content generation for a workflow |
| `insights` | Query analytics, history, and the content brain |
| `process_file` | Send a file through the processing agent for knowledge extraction |

See [`ntangible_mcp/README.md`](ntangible_mcp/README.md) for full tool documentation.

### Control Room (Web UI)

The web dashboard is at: `https://3-21-155-208.nip.io`

Login: `danconnerty@ntangible.co` (ask Elliot for password if needed)

## Local Development

If you need to run the full stack locally:

```bash
# 1. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Set up Postgres
createdb ntangible_marketing

# 3. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 4. Run migrations
alembic upgrade head

# 5. Start the server
python3 -m uvicorn app.main:app --reload
```

## Tests

```bash
pytest
```
