# NTangible Marketing Engine

An AI-powered marketing automation system that:

- **Generates content** across LinkedIn, Instagram, X (Twitter), newsletters, and blogs using Azure OpenAI
- **Manages a knowledge graph** of people, companies, partners, clients, competitors, and their relationships
- **Processes incoming data** (emails, calendar events, files) through a layer-aware pipeline that classifies, extracts, and reasons about knowledge
- **Runs workflows** on cron schedules or manual triggers to produce draft content for review
- **Exposes everything via MCP** so Claude can orchestrate the system directly

## Architecture

Three hosted services run on AWS Lightsail:

- **`ntangible-web`** — FastAPI app serving the Control Room UI and all API endpoints
- **`ntangible-scheduler`** — polls every 15s to fire calendar rules and publish scheduled drafts
- **`ntangible-processor`** — polls every 5s to process new ingestion items through the layer-aware pipeline

The processing pipeline flows through layers:

1. **Intake** — Gmail/Calendar webhooks, MCP file drops, or manual uploads write to the `ingestion_queue`
2. **Pre-filter** — rules drop obvious noise (newsletters, bounces, declined events)
3. **Stage 1 classifier** — LLM call extracts entities, knowledge kind (fact/event/task/deadline/observation), topic, and confidence
4. **Stage 2 intelligence** — LLM call reasons about how new knowledge connects to the existing graph, producing edges, contradictions, and implications
5. **Graph write** — typed knowledge nodes and edges are persisted

---

## Quick Start (MCP with Claude Code)

The fastest way to use the system is through the MCP server in Claude Code. It connects to the hosted production API — no local server or database required.

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
- "What does the brain know about Alliance Sports?"

### MCP Tools

| Tool | Description |
|------|-------------|
| `health` | Check API status and queue counts |
| `workflows` | List, create, pause, resume workflows |
| `drafts` | Review queue — list, approve, reject drafts |
| `manual_request` | Trigger content generation for a workflow |
| `insights` | Query analytics, history, and the content brain |
| `process_file` | Send a file through the processing agent for knowledge extraction |
| `get_context` | Query the knowledge graph for entities, knowledge, and relationships |

See [`ntangible_mcp/README.md`](ntangible_mcp/README.md) for full tool documentation.

---

## Control Room (Web UI)

The web dashboard is at: `https://3-21-155-208.nip.io`

Login with your Cognito account (ask Elliot for access).

**What you'll see:**

- **Brain** (default view) — knowledge graph visualization, topic-filtered views, recent activity
  - **Graph** — force-directed visualization of entities and relationships
  - **Knowledge** — searchable list of facts, events, tasks, drafts, observations
  - **Review** — human approval queue for extracted knowledge
  - **Sources** — configured content sources (web, social, partner pages)
  - **Topics** — entities and knowledge filtered by topic (Marketing, Work, People, Projects, Finance)
  - **Settings** — connect Gmail/Calendar, configure alert channels, view processing queue stats
- **Marketing** — workflow management, draft review, analytics, campaigns, partner/competitor intel

---

## Local Development

Only needed if you want to run the full stack yourself instead of using the hosted version.

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

The app will be at `http://localhost:8000`.

## Tests

```bash
pytest
```
