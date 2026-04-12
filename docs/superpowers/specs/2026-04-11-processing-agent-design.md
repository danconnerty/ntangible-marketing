# Processing Agent Design Spec

**Date:** 2026-04-11
**Status:** Draft
**Scope:** Knowledge ingestion, classification, and routing pipeline for the NTangible Marketing Engine

## Overview

A hosted processing agent that ingests data from connected accounts (Gmail, Google Calendar) and manual inputs (MCP file drops, UI uploads), classifies each item, and routes it through modular handlers for knowledge extraction, workflow triggering, and alerting.

## Goals

- Ingest unstructured data (emails, calendar events, documents) into the knowledge graph automatically
- Classify incoming items to determine if they contain knowledge, should trigger workflows, or warrant user alerts
- Process in near real-time — items are handled within seconds of arrival via webhooks
- Keep LLM costs under $5/month at expected volume (~100 items/day)
- Modular handler architecture — each output path (knowledge, workflow, alert) can be changed independently

## Non-Goals

- Actual notification delivery (Telegram/WhatsApp/Slack are mock implementations for now)
- Multi-tenant support (single Gmail/Calendar per system)
- Historical email backfill (new items only)
- Attachment parsing (text content only for v1)
- Notification importance thresholds or user preferences

---

## Architecture

### System Overview

```
INTAKE SOURCES → INGESTION QUEUE → PRE-FILTER → CLASSIFIER → HANDLERS
```

All intake sources write to a single `ingestion_queue` Postgres table. A dedicated `ntangible-processor` systemd service polls the queue every 5 seconds, runs items through a rules-based pre-filter, then an LLM classifier, then routes to modular handlers.

### Components

#### 1. Intake Sources

**Gmail (webhook-based):**
- User connects via OAuth2 in Brain Settings (scope: `gmail.readonly`)
- On auth, we create a Gmail watch via the API — Google sends push notifications to `POST /webhooks/gmail` via Pub/Sub
- Webhook receives a history ID → we fetch the email content via Gmail API using stored refresh token → write to `ingestion_queue`
- Gmail watches expire every 7 days — the existing scheduler auto-renews them

**Google Calendar (webhook-based):**
- User connects via OAuth2 (scopes: `calendar.readonly`, `calendar.events.readonly`)
- We set up a watch channel on the primary calendar → Google pushes to `POST /webhooks/calendar`
- Webhook receives a sync token → we fetch changed events via Calendar API → write to `ingestion_queue`
- Calendar watches also require periodic renewal

**MCP File Drops:**
- New MCP tool: `process_file` — accepts file content and metadata
- Writes directly to `ingestion_queue` with `source_type: "mcp_file"`
- Uses existing MCP auth, no OAuth needed

**Manual Upload (Settings UI):**
- File upload form in Brain Settings page
- Writes to `ingestion_queue` with `source_type: "manual_upload"`

#### 2. Ingestion Queue

Postgres table: `ingestion_queue`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| source_type | String(32) | `gmail`, `calendar`, `mcp_file`, `manual_upload` |
| source_id | String(512) | Deduplication key (message ID, event ID, file hash) |
| raw_payload | JSONB | Full raw content (email body, event data, file text) |
| status | String(32) | `pending`, `processing`, `completed`, `filtered`, `failed` |
| claimed_at | DateTime | Lock timestamp (same pattern as scheduler) |
| claimed_by | String(128) | Worker ID |
| processed_at | DateTime | Completion timestamp |
| classification | JSONB | Classifier output |
| result | JSONB | Handler results |
| error | Text | Error message if failed |
| created_at | DateTime | When the item was queued |

Unique constraint on `(source_type, source_id)` prevents duplicate processing.

#### 3. Rules Pre-Filter

Runs before the LLM classifier. Free, instant. Marks obvious noise as `status: "filtered"` without spending an LLM call.

Rules:
- **Email:** skip auto-unsubscribe, newsletters (List-Unsubscribe header), bounces, spam-scored messages, declined calendar RSVPs embedded in email
- **Calendar:** skip declined events, cancelled events, all-day "OOO" events

Note: deduplication is handled at the DB level via the unique constraint on `(source_type, source_id)` — no pre-filter rule needed.

Estimated reduction: 30-50% of incoming items never hit the LLM.

#### 4. LLM Classifier

Single call to gpt-5.4-nano (Azure OpenAI) with structured JSON output per item.

**Input context provided to the LLM:**
- Raw item content (email body, calendar event, file text)
- Source type
- List of currently active workflows with their names and descriptions
- List of existing entity types in the graph

**Structured output schema:**

```json
{
  "summary": "One-line summary of the item",
  "is_knowledge": true,
  "knowledge_entities": [
    {"name": "Alliance Sports", "type": "company", "relation": "meeting scheduled"},
    {"name": "Dan Connerty", "type": "person", "relation": "attendee"}
  ],
  "is_workflow_trigger": true,
  "workflow_slugs": ["partner-update"],
  "workflow_reason": "New partner meeting scheduled",
  "is_alert": false,
  "alert_reason": null
}
```

An item can be classified as any combination of knowledge, workflow trigger, and alert simultaneously. The classifier output is stored in the `classification` JSONB column for audit.

#### 5. Modular Handlers

Each handler is a standalone Python module with a single entry point:

```python
def handle(item: IngestionQueueItem, classification: dict) -> HandlerResult
```

Handlers share no state. The processor routes to each applicable handler based on the classification flags.

**Knowledge Handler** (`app/services/processor/handlers/knowledge.py`):
- Receives the entity preview from the classifier
- Entity resolution pipeline:
  1. Exact slug match against existing EntityNodes
  2. Fuzzy name match using Postgres trigram similarity (pg_trgm)
  3. If no match found, create new EntityNode
- Creates EntityEdges for relationships between resolved entities
- Creates a KnowledgeNode with the summary, source reference, confidence score, and temporal validity
- For items >500 words: makes a second, deeper LLM extraction call to catch additional entities
- Writes all results to the graph

**Workflow Handler** (`app/services/processor/handlers/workflow.py`):
- Receives `workflow_slugs` from the classifier
- Validates each slug against active workflows in the DB
- Triggers matched workflows via the existing trigger system
- Logs the trigger reason for audit

**Alert Handler** (`app/services/processor/handlers/alert.py`):
- Receives `alert_reason` from the classifier
- Formats a message from the classifier summary
- Sends via the configured alert channel
- Mock implementation for v1 — logs the alert but doesn't actually send

#### 6. Processor Service

New systemd service: `ntangible-processor`

- Polls `ingestion_queue` for `status: "pending"` items every 5 seconds
- Claims items using the same lock pattern as the scheduler (claimed_at + claimed_by with 15-minute timeout)
- For each claimed item:
  1. Run pre-filter rules → if noise, mark as `filtered` and skip
  2. Call LLM classifier → store classification
  3. Route to applicable handlers based on classification flags
  4. Store handler results in `result` JSONB
  5. Mark as `completed` (or `failed` with error)

---

## Brain Settings Page

New page at `/control-room/brain/settings` under the Brain section nav.

### Sections

**Intake Connections:**
- Gmail card: Connect/Disconnect button, shows connected email when active
- Google Calendar card: Connect/Disconnect button, shows calendar name when active
- OAuth flow: redirect to Google consent → callback stores tokens in `app_connections`

**Alert Channels:**
- Telegram card: Connect/Disconnect (mock for v1)
- WhatsApp card: "Coming soon" placeholder
- Slack card: "Coming soon" placeholder

**Processing Queue Dashboard:**
- Counts: processed today, pending, errors
- Simple stats, no charts

**Recent Activity Feed:**
- Last ~20 processed items
- Shows: timestamp, source description, which handlers fired, entity count

---

## Google OAuth

**Requirements:**
- Google Cloud project with Gmail API and Calendar API enabled
- OAuth2 client credentials (Client ID + Client Secret)
- Authorized redirect URI: `https://3-21-155-208.nip.io/control-room/brain/settings/oauth/callback`

**New `.env` variables:**

```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

**Token storage:**
- Stored in the existing `app_connections` table
- Fields needed: `provider` (google), `access_token`, `refresh_token`, `token_expiry`, `scopes`, `connected_email`
- Tokens refreshed automatically when expired using the refresh token

**Watch management:**
- Gmail watch created on connect, renewed every 6 days by the scheduler
- Calendar watch channel created on connect, renewed before expiry
- Watches deleted on disconnect

---

## New MCP Tool

```
process_file
  - file_content (string, required): The text content to process
  - file_name (string, required): Original filename for context
  - file_type (string, optional): MIME type hint
```

Writes to `ingestion_queue` with `source_type: "mcp_file"` and `source_id` as SHA256 of content (dedup).

---

## File Structure

```
app/services/processor/
├── __init__.py
├── classifier.py          # Rules pre-filter + LLM classification
├── processor.py           # Main loop: dequeue → classify → route
└── handlers/
    ├── __init__.py
    ├── base.py            # HandlerResult dataclass/protocol
    ├── knowledge.py       # Entity extraction → graph writes
    ├── workflow.py        # Match workflows → trigger runs
    └── alert.py           # Format → send (mock for v1)

app/api/
├── webhook_routes.py      # POST /webhooks/gmail, /webhooks/calendar
└── brain_settings_routes.py  # OAuth flow + settings API

app/web/
└── brain_settings.py      # Settings page UI routes + templates

app/templates/brain/
└── settings.html          # Brain Settings page template

ntangible_mcp/
└── server.py              # Add process_file tool
```

---

## Database Migration

New table: `ingestion_queue` (see schema in Section 2)

Modify `app_connections`: the table already exists with `credential_json` (JSONB) and `config_json` (JSONB) columns that can store OAuth tokens and watch metadata. However, the `channel` enum (`ConnectionChannel`) needs new values: `gmail`, `calendar`, `telegram`. This requires an Alembic migration to extend the enum.

Token storage plan:
- `credential_json`: `{"access_token": "...", "refresh_token": "...", "token_expiry": "..."}`
- `config_json`: `{"scopes": [...], "connected_email": "...", "watch_id": "...", "watch_expiry": "..."}`

---

## Deployment

- New systemd unit: `ntangible-processor.service` on Lightsail
- Webhook endpoints require HTTPS (already have via Let's Encrypt on nip.io)
- Google Pub/Sub topic + subscription for Gmail push notifications
- Deploy script updated to restart `ntangible-processor` alongside `ntangible-web` and `ntangible-scheduler`

---

## Cost Estimate

| Component | Monthly Cost |
|-----------|-------------|
| LLM classifier (gpt-5.4-nano, ~100 items/day after pre-filter) | ~$3-5 |
| Deep extraction calls (~10% of items) | ~$0.50-1 |
| Infrastructure (existing Lightsail) | $0 |
| Google APIs (Gmail, Calendar) | Free tier |
| **Total** | **~$4-6/month** |
