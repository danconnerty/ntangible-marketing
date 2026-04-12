# Processing Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hosted processing agent that ingests data from Gmail, Google Calendar, MCP file drops, and manual uploads, classifies each item via rules + LLM, and routes to modular handlers for knowledge extraction, workflow triggering, and alerting.

**Architecture:** Webhook receivers on FastAPI write to an `ingestion_queue` Postgres table. A separate `ntangible-processor` systemd service polls the queue, runs a rules pre-filter, then an LLM classifier (gpt-5.4-nano via Azure OpenAI), then routes to modular handlers (knowledge, workflow, alert). Brain Settings UI manages OAuth connections and shows processing activity.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Alembic, Azure OpenAI (gpt-5.4-nano), Google Gmail API, Google Calendar API, Google OAuth2

**Spec:** `docs/superpowers/specs/2026-04-11-processing-agent-design.md`

---

## File Structure

```
# New files
app/models/ingestion.py                          # IngestionQueueItem model
app/services/processor/__init__.py
app/services/processor/prefilter.py              # Rules-based noise filter
app/services/processor/classifier.py             # LLM classification
app/services/processor/processor.py              # Main loop: dequeue → classify → route
app/services/processor/handlers/__init__.py
app/services/processor/handlers/base.py          # HandlerResult dataclass
app/services/processor/handlers/knowledge.py     # Entity extraction → graph writes
app/services/processor/handlers/workflow.py      # Match workflows → trigger runs
app/services/processor/handlers/alert.py         # Mock alert handler
app/api/webhook_routes.py                        # POST /webhooks/gmail, /webhooks/calendar
app/api/brain_settings_routes.py                 # OAuth flow + settings API endpoints
app/web/brain_settings.py                        # Settings page web routes
app/web/templates/brain/settings.html            # Brain Settings page template
app/services/google_oauth.py                     # Google OAuth2 token management
app/services/gmail_intake.py                     # Gmail message fetching
app/services/calendar_intake.py                  # Calendar event fetching
scripts/run_processor.py                         # Entrypoint for ntangible-processor service
alembic/versions/20260411_add_ingestion_queue.py  # Migration
tests/test_ingestion_model.py
tests/test_prefilter.py
tests/test_classifier.py
tests/test_knowledge_handler.py
tests/test_workflow_handler.py
tests/test_alert_handler.py
tests/test_processor.py
tests/test_webhook_routes.py
tests/test_brain_settings_routes.py
tests/test_mcp_process_file.py

# Modified files
app/models/publishing_connection.py              # Add GMAIL, CALENDAR, TELEGRAM to ConnectionChannel enum
app/config.py                                    # Add google_client_id, google_client_secret settings
app/main.py                                      # Register webhook_routes, brain_settings_routes, brain_settings web routes
app/web/templates/base.html                      # Add "Settings" link to brain sidebar nav
ntangible_mcp/server.py                          # Add process_file tool
ntangible_mcp/client.py                          # Add post_file method
.env.example                                     # Add GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
```

---

### Task 1: Ingestion Queue Model + Migration

**Files:**
- Create: `app/models/ingestion.py`
- Create: `alembic/versions/20260411_add_ingestion_queue.py`
- Modify: `app/models/publishing_connection.py`
- Test: `tests/test_ingestion_model.py`

- [ ] **Step 1: Write the model test**

```python
# tests/test_ingestion_model.py
import uuid
from datetime import datetime, timezone

from app.models.ingestion import IngestionQueueItem, IngestionStatus, IngestionSourceType


def test_ingestion_queue_item_defaults():
    item = IngestionQueueItem(
        source_type=IngestionSourceType.GMAIL,
        source_id="msg-abc-123",
        raw_payload={"subject": "Hello", "body": "World"},
    )
    assert item.source_type == IngestionSourceType.GMAIL
    assert item.source_id == "msg-abc-123"
    assert item.status == IngestionStatus.PENDING
    assert item.raw_payload == {"subject": "Hello", "body": "World"}
    assert item.claimed_at is None
    assert item.classification is None
    assert item.result is None
    assert item.error is None


def test_ingestion_source_types():
    assert IngestionSourceType.GMAIL.value == "gmail"
    assert IngestionSourceType.CALENDAR.value == "calendar"
    assert IngestionSourceType.MCP_FILE.value == "mcp_file"
    assert IngestionSourceType.MANUAL_UPLOAD.value == "manual_upload"


def test_ingestion_statuses():
    assert IngestionStatus.PENDING.value == "pending"
    assert IngestionStatus.PROCESSING.value == "processing"
    assert IngestionStatus.COMPLETED.value == "completed"
    assert IngestionStatus.FILTERED.value == "filtered"
    assert IngestionStatus.FAILED.value == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/elliot18/Desktop/Home/Projects/ntangible_marketing && .venv/bin/pytest tests/test_ingestion_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.ingestion'`

- [ ] **Step 3: Create the model**

```python
# app/models/ingestion.py
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IngestionSourceType(str, enum.Enum):
    GMAIL = "gmail"
    CALENDAR = "calendar"
    MCP_FILE = "mcp_file"
    MANUAL_UPLOAD = "manual_upload"


class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FILTERED = "filtered"
    FAILED = "failed"


class IngestionQueueItem(Base):
    __tablename__ = "ingestion_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=IngestionStatus.PENDING.value
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    classification: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # Prevent duplicate processing of the same source item
        {"schema": None},
    )
```

Note: We use plain String columns for `source_type` and `status` instead of Postgres enums to avoid migration complexity. The Python enums provide validation at the application layer.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_ingestion_model.py -v`
Expected: PASS

- [ ] **Step 5: Add ConnectionChannel enum values**

In `app/models/publishing_connection.py`, add three new values to `ConnectionChannel`:

```python
class ConnectionChannel(str, enum.Enum):
    X = "x"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    NEWSLETTER = "newsletter"
    BLOG = "blog"
    GMAIL = "gmail"
    CALENDAR = "calendar"
    TELEGRAM = "telegram"
```

- [ ] **Step 6: Add Google OAuth settings to config**

In `app/config.py`, add inside the `Settings` class after the `canva_brand_template_set` field:

```python
    google_client_id: str = ""
    google_client_secret: str = ""
```

In `.env.example`, add at the bottom:

```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

- [ ] **Step 7: Create the Alembic migration**

```python
# alembic/versions/20260411_add_ingestion_queue.py
"""add ingestion queue table and extend connection channel enum

Revision ID: 20260411_add_ingestion_queue
Revises: 98fbddb3c753
Create Date: 2026-04-11 22:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260411_add_ingestion_queue"
down_revision: Union[str, Sequence[str], None] = "98fbddb3c753"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend the connection_channel_enum with new values
    op.execute("ALTER TYPE connection_channel_enum ADD VALUE IF NOT EXISTS 'gmail'")
    op.execute("ALTER TYPE connection_channel_enum ADD VALUE IF NOT EXISTS 'calendar'")
    op.execute("ALTER TYPE connection_channel_enum ADD VALUE IF NOT EXISTS 'telegram'")

    # Create ingestion_queue table
    op.create_table(
        "ingestion_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=512), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(length=128), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "classification",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_ingestion_source"),
    )
    # Index for polling pending items
    op.create_index(
        "ix_ingestion_queue_status_created",
        "ingestion_queue",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_queue_status_created", table_name="ingestion_queue")
    op.drop_table("ingestion_queue")
    # Note: cannot remove enum values in PostgreSQL
```

- [ ] **Step 8: Run the migration locally**

Run: `.venv/bin/alembic upgrade head`
Expected: Migration applies successfully

- [ ] **Step 9: Commit**

```bash
git add app/models/ingestion.py alembic/versions/20260411_add_ingestion_queue.py app/models/publishing_connection.py app/config.py .env.example tests/test_ingestion_model.py
git commit -m "feat: add ingestion queue model, migration, and extend connection enum"
```

---

### Task 2: Rules Pre-Filter

**Files:**
- Create: `app/services/processor/prefilter.py`
- Create: `app/services/processor/__init__.py`
- Test: `tests/test_prefilter.py`

- [ ] **Step 1: Write the pre-filter tests**

```python
# tests/test_prefilter.py
from app.services.processor.prefilter import should_filter, FilterReason


def test_filter_unsubscribe_email():
    item = {
        "source_type": "gmail",
        "raw_payload": {
            "headers": {"List-Unsubscribe": "<mailto:unsub@example.com>"},
            "subject": "Weekly deals",
            "body": "Buy stuff",
        },
    }
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is not None
    assert result.reason == "newsletter_unsubscribe"


def test_filter_bounce_email():
    item = {
        "source_type": "gmail",
        "raw_payload": {
            "headers": {},
            "from": "mailer-daemon@google.com",
            "subject": "Delivery failed",
            "body": "Message not delivered",
        },
    }
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is not None
    assert result.reason == "bounce"


def test_filter_noreply_email():
    item = {
        "source_type": "gmail",
        "raw_payload": {
            "headers": {},
            "from": "noreply@somecompany.com",
            "subject": "Your receipt",
            "body": "Thanks for your purchase",
        },
    }
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is not None
    assert result.reason == "noreply_sender"


def test_pass_real_email():
    item = {
        "source_type": "gmail",
        "raw_payload": {
            "headers": {},
            "from": "dan@partner.co",
            "subject": "Partnership update",
            "body": "Here's the latest on our project...",
        },
    }
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is None


def test_filter_cancelled_calendar_event():
    item = {
        "source_type": "calendar",
        "raw_payload": {
            "status": "cancelled",
            "summary": "Team standup",
        },
    }
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is not None
    assert result.reason == "cancelled_event"


def test_filter_declined_calendar_event():
    item = {
        "source_type": "calendar",
        "raw_payload": {
            "status": "confirmed",
            "summary": "Team standup",
            "attendees": [
                {"email": "elliot@ntangible.com", "responseStatus": "declined"}
            ],
            "self_email": "elliot@ntangible.com",
        },
    }
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is not None
    assert result.reason == "declined_event"


def test_pass_real_calendar_event():
    item = {
        "source_type": "calendar",
        "raw_payload": {
            "status": "confirmed",
            "summary": "Meeting with Alliance Sports",
            "attendees": [
                {"email": "elliot@ntangible.com", "responseStatus": "accepted"}
            ],
            "self_email": "elliot@ntangible.com",
        },
    }
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is None


def test_pass_mcp_file_always():
    item = {
        "source_type": "mcp_file",
        "raw_payload": {"file_name": "doc.pdf", "content": "Some text"},
    }
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is None


def test_pass_manual_upload_always():
    item = {
        "source_type": "manual_upload",
        "raw_payload": {"file_name": "notes.txt", "content": "Some notes"},
    }
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_prefilter.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the pre-filter**

```python
# app/services/processor/__init__.py
```

```python
# app/services/processor/prefilter.py
"""Rules-based noise filter. Runs before the LLM classifier to skip obvious junk."""

from __future__ import annotations

from dataclasses import dataclass

BOUNCE_SENDERS = {"mailer-daemon", "postmaster"}
NOREPLY_PATTERNS = {"noreply@", "no-reply@", "donotreply@", "do-not-reply@"}


@dataclass
class FilterReason:
    reason: str
    detail: str


def should_filter(source_type: str, raw_payload: dict) -> FilterReason | None:
    """Return a FilterReason if the item should be skipped, or None to process it."""
    if source_type == "gmail":
        return _filter_email(raw_payload)
    if source_type == "calendar":
        return _filter_calendar(raw_payload)
    # MCP files and manual uploads always pass through
    return None


def _filter_email(payload: dict) -> FilterReason | None:
    headers = payload.get("headers", {})

    # Newsletter / mailing list
    if headers.get("List-Unsubscribe"):
        return FilterReason("newsletter_unsubscribe", "Has List-Unsubscribe header")

    sender = (payload.get("from") or "").lower()

    # Bounce messages
    sender_local = sender.split("@")[0] if "@" in sender else sender
    if sender_local in BOUNCE_SENDERS:
        return FilterReason("bounce", f"Bounce sender: {sender}")

    # No-reply addresses
    for pattern in NOREPLY_PATTERNS:
        if pattern in sender:
            return FilterReason("noreply_sender", f"No-reply sender: {sender}")

    return None


def _filter_calendar(payload: dict) -> FilterReason | None:
    status = payload.get("status", "").lower()

    if status == "cancelled":
        return FilterReason("cancelled_event", "Event was cancelled")

    # Check if self declined
    self_email = payload.get("self_email", "").lower()
    if self_email:
        attendees = payload.get("attendees", [])
        for attendee in attendees:
            if attendee.get("email", "").lower() == self_email:
                if attendee.get("responseStatus") == "declined":
                    return FilterReason("declined_event", "User declined this event")

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_prefilter.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/processor/__init__.py app/services/processor/prefilter.py tests/test_prefilter.py
git commit -m "feat: add rules-based pre-filter for ingestion queue"
```

---

### Task 3: LLM Classifier

**Files:**
- Create: `app/services/processor/classifier.py`
- Test: `tests/test_classifier.py`

- [ ] **Step 1: Write the classifier tests**

```python
# tests/test_classifier.py
import json
from unittest.mock import patch, MagicMock

from app.services.processor.classifier import (
    classify_item,
    build_classifier_prompt,
    parse_classification,
    ClassificationResult,
)


def test_build_classifier_prompt_email():
    payload = {
        "from": "dan@partner.co",
        "subject": "Partnership update",
        "body": "Here's the latest on our project with Alliance Sports...",
    }
    workflows = [
        {"slug": "partner-update", "name": "Partner Update", "description": "Updates about partners"},
        {"slug": "linkedin-company-update", "name": "LinkedIn Company Update", "description": "LinkedIn posts"},
    ]
    entity_types = ["company", "person", "partner", "topic"]

    system_prompt, user_prompt = build_classifier_prompt(
        source_type="gmail",
        raw_payload=payload,
        active_workflows=workflows,
        entity_types=entity_types,
    )

    assert "gmail" in user_prompt.lower()
    assert "dan@partner.co" in user_prompt
    assert "partner-update" in system_prompt
    assert "company" in system_prompt


def test_parse_classification_valid():
    raw = {
        "summary": "Partnership update from Dan about Alliance Sports",
        "is_knowledge": True,
        "knowledge_entities": [
            {"name": "Alliance Sports", "type": "company", "relation": "partnership update"},
            {"name": "Dan Connerty", "type": "person", "relation": "sender"},
        ],
        "is_workflow_trigger": True,
        "workflow_slugs": ["partner-update"],
        "workflow_reason": "Partner relationship update",
        "is_alert": False,
        "alert_reason": None,
    }
    result = parse_classification(raw)
    assert isinstance(result, ClassificationResult)
    assert result.is_knowledge is True
    assert len(result.knowledge_entities) == 2
    assert result.knowledge_entities[0]["name"] == "Alliance Sports"
    assert result.is_workflow_trigger is True
    assert result.workflow_slugs == ["partner-update"]
    assert result.is_alert is False


def test_parse_classification_minimal():
    raw = {
        "summary": "Junk email",
        "is_knowledge": False,
        "knowledge_entities": [],
        "is_workflow_trigger": False,
        "workflow_slugs": [],
        "workflow_reason": None,
        "is_alert": False,
        "alert_reason": None,
    }
    result = parse_classification(raw)
    assert result.is_knowledge is False
    assert result.is_workflow_trigger is False
    assert result.is_alert is False


def test_classify_item_calls_llm():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "summary": "Test email",
        "is_knowledge": True,
        "knowledge_entities": [{"name": "Test Co", "type": "company", "relation": "mentioned"}],
        "is_workflow_trigger": False,
        "workflow_slugs": [],
        "workflow_reason": None,
        "is_alert": False,
        "alert_reason": None,
    })
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch("app.services.processor.classifier._get_openai_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response

        result = classify_item(
            source_type="gmail",
            raw_payload={"from": "test@test.com", "subject": "Test", "body": "Hello"},
            active_workflows=[],
            entity_types=["company"],
        )

    assert result.is_knowledge is True
    assert result.knowledge_entities[0]["name"] == "Test Co"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the classifier**

```python
# app/services/processor/classifier.py
"""LLM-based classifier for ingestion queue items.

Makes a single gpt-5.4-nano call per item to classify it as knowledge,
workflow trigger, alert, or any combination of the three.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from openai import AzureOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    summary: str
    is_knowledge: bool
    knowledge_entities: list[dict] = field(default_factory=list)
    is_workflow_trigger: bool = False
    workflow_slugs: list[str] = field(default_factory=list)
    workflow_reason: str | None = None
    is_alert: bool = False
    alert_reason: str | None = None


def _get_openai_client() -> AzureOpenAI:
    settings = get_settings()
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )


def build_classifier_prompt(
    *,
    source_type: str,
    raw_payload: dict,
    active_workflows: list[dict],
    entity_types: list[str],
) -> tuple[str, str]:
    """Build the system and user prompts for classification."""

    workflow_list = "\n".join(
        f"- {w['slug']}: {w.get('description') or w.get('name', '')}"
        for w in active_workflows
    ) or "No active workflows."

    entity_type_list = ", ".join(entity_types) or "none defined"

    system_prompt = f"""You are a knowledge processing agent for a marketing engine.
You receive incoming data (emails, calendar events, documents) and classify each item.

For each item, determine ALL that apply:

1. KNOWLEDGE: Does this contain information worth storing in our knowledge graph?
   Extract entities (people, companies, topics, etc.) and their relationships.
   Focus on WHO, WHAT, WHEN, WHERE — not the raw content itself.

2. WORKFLOW TRIGGER: Should this trigger any of these active workflows?
   Active workflows:
   {workflow_list}
   Only trigger a workflow if the content is clearly relevant to it.

3. ALERT: Is this important enough to notify the user immediately?
   Only flag as alert for time-sensitive or high-importance items.

Known entity types in our graph: {entity_type_list}

Respond with valid JSON matching this exact schema:
{{
  "summary": "one-line summary",
  "is_knowledge": true/false,
  "knowledge_entities": [{{"name": "...", "type": "...", "relation": "..."}}],
  "is_workflow_trigger": true/false,
  "workflow_slugs": ["slug1"],
  "workflow_reason": "why this triggers the workflow" or null,
  "is_alert": true/false,
  "alert_reason": "why this is urgent" or null
}}"""

    # Build user prompt with the actual content
    if source_type == "gmail":
        sender = raw_payload.get("from", "unknown")
        subject = raw_payload.get("subject", "")
        body = raw_payload.get("body", "")
        user_prompt = f"Source: gmail\nFrom: {sender}\nSubject: {subject}\n\n{body}"
    elif source_type == "calendar":
        summary = raw_payload.get("summary", "")
        description = raw_payload.get("description", "")
        start = raw_payload.get("start", "")
        attendees = raw_payload.get("attendees", [])
        attendee_str = ", ".join(a.get("email", "") for a in attendees)
        user_prompt = (
            f"Source: calendar\nEvent: {summary}\nWhen: {start}\n"
            f"Attendees: {attendee_str}\n\n{description}"
        )
    else:
        file_name = raw_payload.get("file_name", "unknown")
        content = raw_payload.get("content", "")
        user_prompt = f"Source: {source_type}\nFile: {file_name}\n\n{content}"

    # Truncate very long content to save tokens
    if len(user_prompt) > 8000:
        user_prompt = user_prompt[:8000] + "\n\n[TRUNCATED]"

    return system_prompt, user_prompt


def parse_classification(raw: dict) -> ClassificationResult:
    """Parse raw JSON dict into a ClassificationResult."""
    return ClassificationResult(
        summary=raw.get("summary", ""),
        is_knowledge=bool(raw.get("is_knowledge", False)),
        knowledge_entities=raw.get("knowledge_entities", []),
        is_workflow_trigger=bool(raw.get("is_workflow_trigger", False)),
        workflow_slugs=raw.get("workflow_slugs", []),
        workflow_reason=raw.get("workflow_reason"),
        is_alert=bool(raw.get("is_alert", False)),
        alert_reason=raw.get("alert_reason"),
    )


def classify_item(
    *,
    source_type: str,
    raw_payload: dict,
    active_workflows: list[dict],
    entity_types: list[str],
) -> ClassificationResult:
    """Classify an ingestion queue item via a single LLM call."""
    settings = get_settings()
    client = _get_openai_client()

    system_prompt, user_prompt = build_classifier_prompt(
        source_type=source_type,
        raw_payload=raw_payload,
        active_workflows=active_workflows,
        entity_types=entity_types,
    )

    response = client.chat.completions.create(
        model=settings.azure_openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_completion_tokens=512,
        temperature=0.1,
    )

    raw_text = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    logger.info(
        "Classifier LLM call: %d prompt tokens, %d completion tokens",
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
    )

    parsed = json.loads(raw_text)
    return parse_classification(parsed)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_classifier.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/processor/classifier.py tests/test_classifier.py
git commit -m "feat: add LLM classifier for ingestion items"
```

---

### Task 4: Handler Base + Alert Handler (Mock)

**Files:**
- Create: `app/services/processor/handlers/__init__.py`
- Create: `app/services/processor/handlers/base.py`
- Create: `app/services/processor/handlers/alert.py`
- Test: `tests/test_alert_handler.py`

- [ ] **Step 1: Write the tests**

```python
# tests/test_alert_handler.py
from app.services.processor.handlers.base import HandlerResult
from app.services.processor.handlers.alert import handle
from app.services.processor.classifier import ClassificationResult


def test_alert_handler_when_alert():
    classification = ClassificationResult(
        summary="Urgent partner request",
        is_knowledge=False,
        is_alert=True,
        alert_reason="Time-sensitive partnership decision needed",
    )
    result = handle(
        raw_payload={"from": "dan@partner.co", "subject": "Urgent"},
        classification=classification,
    )
    assert isinstance(result, HandlerResult)
    assert result.handler_name == "alert"
    assert result.success is True
    assert result.detail["mock"] is True
    assert "Time-sensitive" in result.detail["message"]


def test_alert_handler_when_not_alert():
    classification = ClassificationResult(
        summary="Regular email",
        is_knowledge=True,
        is_alert=False,
    )
    result = handle(
        raw_payload={"from": "dan@partner.co", "subject": "Update"},
        classification=classification,
    )
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_alert_handler.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the base and alert handler**

```python
# app/services/processor/handlers/__init__.py
```

```python
# app/services/processor/handlers/base.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HandlerResult:
    handler_name: str
    success: bool
    detail: dict = field(default_factory=dict)
    error: str | None = None
```

```python
# app/services/processor/handlers/alert.py
"""Mock alert handler. Logs alert but does not send."""

from __future__ import annotations

import logging

from app.services.processor.classifier import ClassificationResult
from app.services.processor.handlers.base import HandlerResult

logger = logging.getLogger(__name__)


def handle(
    *,
    raw_payload: dict,
    classification: ClassificationResult,
) -> HandlerResult | None:
    """Send an alert if the classification flags it. Mock for v1."""
    if not classification.is_alert:
        return None

    message = classification.alert_reason or classification.summary

    logger.info("MOCK ALERT: %s", message)

    return HandlerResult(
        handler_name="alert",
        success=True,
        detail={
            "mock": True,
            "message": message,
            "channel": "telegram",
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_alert_handler.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/processor/handlers/__init__.py app/services/processor/handlers/base.py app/services/processor/handlers/alert.py tests/test_alert_handler.py
git commit -m "feat: add handler base and mock alert handler"
```

---

### Task 5: Workflow Handler

**Files:**
- Create: `app/services/processor/handlers/workflow.py`
- Test: `tests/test_workflow_handler.py`

- [ ] **Step 1: Write the tests**

```python
# tests/test_workflow_handler.py
from unittest.mock import MagicMock, patch

from app.services.processor.handlers.workflow import handle
from app.services.processor.handlers.base import HandlerResult
from app.services.processor.classifier import ClassificationResult


def test_workflow_handler_triggers_matching_workflow():
    classification = ClassificationResult(
        summary="Partner update email",
        is_knowledge=False,
        is_workflow_trigger=True,
        workflow_slugs=["partner-update"],
        workflow_reason="Partner relationship update",
    )

    mock_db = MagicMock()
    # Mock finding the workflow entity
    mock_workflow = MagicMock()
    mock_workflow.slug = "partner-update"
    mock_workflow.canonical_name = "Partner Update"
    mock_workflow.id = "wf-123"

    with patch("app.services.processor.handlers.workflow.BrainQuery") as MockBQ:
        mock_bq = MockBQ.return_value
        mock_bq.get_entity_by_slug.return_value = mock_workflow

        result = handle(
            db=mock_db,
            raw_payload={"subject": "Update"},
            classification=classification,
        )

    assert isinstance(result, HandlerResult)
    assert result.handler_name == "workflow"
    assert result.success is True
    assert "partner-update" in result.detail["triggered"]


def test_workflow_handler_skips_unknown_slugs():
    classification = ClassificationResult(
        summary="Email about unknown workflow",
        is_knowledge=False,
        is_workflow_trigger=True,
        workflow_slugs=["nonexistent-workflow"],
        workflow_reason="Trigger reason",
    )

    mock_db = MagicMock()

    with patch("app.services.processor.handlers.workflow.BrainQuery") as MockBQ:
        mock_bq = MockBQ.return_value
        mock_bq.get_entity_by_slug.return_value = None

        result = handle(
            db=mock_db,
            raw_payload={"subject": "Update"},
            classification=classification,
        )

    assert result.detail["skipped"] == ["nonexistent-workflow"]


def test_workflow_handler_not_triggered():
    classification = ClassificationResult(
        summary="Regular email",
        is_knowledge=True,
        is_workflow_trigger=False,
    )

    result = handle(
        db=MagicMock(),
        raw_payload={"subject": "Update"},
        classification=classification,
    )
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_workflow_handler.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the workflow handler**

```python
# app/services/processor/handlers/workflow.py
"""Workflow trigger handler. Matches classifier output to active workflows."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.services.brain_query import BrainQuery
from app.services.processor.classifier import ClassificationResult
from app.services.processor.handlers.base import HandlerResult

logger = logging.getLogger(__name__)


def handle(
    *,
    db: Session,
    raw_payload: dict,
    classification: ClassificationResult,
) -> HandlerResult | None:
    """Trigger workflows that match the classifier's workflow_slugs."""
    if not classification.is_workflow_trigger:
        return None

    bq = BrainQuery(db)
    triggered = []
    skipped = []

    for slug in classification.workflow_slugs:
        workflow = bq.get_entity_by_slug("workflow", slug)
        if workflow is None:
            logger.warning("Classifier suggested workflow '%s' but it doesn't exist", slug)
            skipped.append(slug)
            continue

        # Create a KnowledgeNode trigger record
        trigger = bq.create_knowledge_node(
            kind="ingestion_trigger",
            title=f"Ingestion trigger: {classification.summary}",
            content=classification.workflow_reason or "",
            metadata={
                "workflow_slug": slug,
                "workflow_entity_id": str(workflow.id),
                "trigger_source": "processor",
                "classification_summary": classification.summary,
            },
        )

        logger.info(
            "Triggered workflow '%s' from ingestion: %s (trigger_id=%s)",
            slug,
            classification.workflow_reason,
            trigger.id,
        )
        triggered.append(slug)

    return HandlerResult(
        handler_name="workflow",
        success=True,
        detail={
            "triggered": triggered,
            "skipped": skipped,
            "reason": classification.workflow_reason,
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_workflow_handler.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/processor/handlers/workflow.py tests/test_workflow_handler.py
git commit -m "feat: add workflow trigger handler"
```

---

### Task 6: Knowledge Handler

**Files:**
- Create: `app/services/processor/handlers/knowledge.py`
- Test: `tests/test_knowledge_handler.py`

- [ ] **Step 1: Write the tests**

```python
# tests/test_knowledge_handler.py
from unittest.mock import MagicMock, patch, call

from app.services.processor.handlers.knowledge import handle, resolve_entity
from app.services.processor.handlers.base import HandlerResult
from app.services.processor.classifier import ClassificationResult


def test_knowledge_handler_creates_entities_and_knowledge_node():
    classification = ClassificationResult(
        summary="Meeting with Alliance Sports CEO",
        is_knowledge=True,
        knowledge_entities=[
            {"name": "Alliance Sports", "type": "company", "relation": "meeting partner"},
            {"name": "Dan Connerty", "type": "person", "relation": "attendee"},
        ],
    )

    mock_db = MagicMock()

    with patch("app.services.processor.handlers.knowledge.BrainQuery") as MockBQ:
        mock_bq = MockBQ.return_value
        # First entity: not found, will be created
        mock_bq.get_entity_by_slug.side_effect = [None, None]
        mock_entity_1 = MagicMock()
        mock_entity_1.id = "ent-1"
        mock_entity_2 = MagicMock()
        mock_entity_2.id = "ent-2"
        mock_bq.create_entity.side_effect = [mock_entity_1, mock_entity_2]
        mock_knowledge = MagicMock()
        mock_knowledge.id = "kn-1"
        mock_bq.create_knowledge_node.return_value = mock_knowledge

        result = handle(
            db=mock_db,
            raw_payload={"from": "dan@partner.co"},
            classification=classification,
        )

    assert isinstance(result, HandlerResult)
    assert result.handler_name == "knowledge"
    assert result.success is True
    assert result.detail["entities_created"] == 2
    assert result.detail["entities_resolved"] == 0
    assert result.detail["knowledge_node_id"] == "kn-1"


def test_knowledge_handler_resolves_existing_entity():
    classification = ClassificationResult(
        summary="Update from Alliance Sports",
        is_knowledge=True,
        knowledge_entities=[
            {"name": "Alliance Sports", "type": "company", "relation": "update"},
        ],
    )

    mock_db = MagicMock()
    mock_existing = MagicMock()
    mock_existing.id = "existing-ent-1"

    with patch("app.services.processor.handlers.knowledge.BrainQuery") as MockBQ:
        mock_bq = MockBQ.return_value
        mock_bq.get_entity_by_slug.return_value = mock_existing
        mock_knowledge = MagicMock()
        mock_knowledge.id = "kn-1"
        mock_bq.create_knowledge_node.return_value = mock_knowledge

        result = handle(
            db=mock_db,
            raw_payload={"from": "info@alliance.co"},
            classification=classification,
        )

    assert result.detail["entities_created"] == 0
    assert result.detail["entities_resolved"] == 1


def test_knowledge_handler_not_knowledge():
    classification = ClassificationResult(
        summary="Not knowledge",
        is_knowledge=False,
    )
    result = handle(
        db=MagicMock(),
        raw_payload={},
        classification=classification,
    )
    assert result is None


def test_resolve_entity_exact_slug_match():
    mock_bq = MagicMock()
    mock_entity = MagicMock()
    mock_entity.id = "ent-1"
    mock_bq.get_entity_by_slug.return_value = mock_entity

    resolved, created = resolve_entity(
        mock_bq, name="Alliance Sports", entity_type="company"
    )
    assert resolved.id == "ent-1"
    assert created is False


def test_resolve_entity_creates_new():
    mock_bq = MagicMock()
    mock_bq.get_entity_by_slug.return_value = None
    mock_new = MagicMock()
    mock_new.id = "new-ent"
    mock_bq.create_entity.return_value = mock_new

    resolved, created = resolve_entity(
        mock_bq, name="New Company", entity_type="company"
    )
    assert resolved.id == "new-ent"
    assert created is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_knowledge_handler.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the knowledge handler**

```python
# app/services/processor/handlers/knowledge.py
"""Knowledge extraction handler. Resolves entities and writes to the graph."""

from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.services.brain_query import BrainQuery
from app.services.processor.classifier import ClassificationResult
from app.services.processor.handlers.base import HandlerResult

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def resolve_entity(
    bq: BrainQuery,
    *,
    name: str,
    entity_type: str,
) -> tuple:
    """Resolve an entity by slug, or create a new one. Returns (entity, was_created)."""
    slug = _slugify(name)

    # 1. Exact slug match
    existing = bq.get_entity_by_slug(entity_type, slug)
    if existing is not None:
        return existing, False

    # 2. Create new entity
    entity = bq.create_entity(
        entity_type=entity_type,
        canonical_name=name,
        slug=slug,
    )
    logger.info("Created new entity: %s/%s (%s)", entity_type, slug, name)
    return entity, True


def handle(
    *,
    db: Session,
    raw_payload: dict,
    classification: ClassificationResult,
) -> HandlerResult | None:
    """Extract entities from classification and write to the knowledge graph."""
    if not classification.is_knowledge:
        return None

    bq = BrainQuery(db)
    entities_created = 0
    entities_resolved = 0
    resolved_entities = []

    for ent_data in classification.knowledge_entities:
        name = ent_data.get("name", "").strip()
        entity_type = ent_data.get("type", "topic").strip().lower()
        if not name:
            continue

        entity, was_created = resolve_entity(bq, name=name, entity_type=entity_type)
        if was_created:
            entities_created += 1
        else:
            entities_resolved += 1

        resolved_entities.append({
            "entity_id": str(entity.id),
            "name": name,
            "type": entity_type,
            "relation": ent_data.get("relation", ""),
            "created": was_created,
        })

    # Create edges between resolved entities
    edges_created = 0
    for i, ent_a in enumerate(resolved_entities):
        for ent_b in resolved_entities[i + 1:]:
            bq.create_edge(
                source_id=ent_a["entity_id"],
                target_id=ent_b["entity_id"],
                source_type="entity",
                target_type="entity",
                relation=ent_a.get("relation") or "related_to",
            )
            edges_created += 1

    # Create knowledge node as audit record
    knowledge_node = bq.create_knowledge_node(
        kind="ingestion_knowledge",
        title=classification.summary,
        content=f"Source: {raw_payload.get('from', raw_payload.get('file_name', 'unknown'))}",
        metadata={
            "entities": resolved_entities,
            "source_type": raw_payload.get("source_type", "unknown"),
        },
    )

    logger.info(
        "Knowledge handler: %d entities (%d new, %d resolved), %d edges, knowledge_node=%s",
        len(resolved_entities),
        entities_created,
        entities_resolved,
        edges_created,
        knowledge_node.id,
    )

    return HandlerResult(
        handler_name="knowledge",
        success=True,
        detail={
            "entities_created": entities_created,
            "entities_resolved": entities_resolved,
            "edges_created": edges_created,
            "entities": resolved_entities,
            "knowledge_node_id": str(knowledge_node.id),
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_knowledge_handler.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/processor/handlers/knowledge.py tests/test_knowledge_handler.py
git commit -m "feat: add knowledge extraction handler with entity resolution"
```

---

### Task 7: Main Processor Service

**Files:**
- Create: `app/services/processor/processor.py`
- Create: `scripts/run_processor.py`
- Test: `tests/test_processor.py`

- [ ] **Step 1: Write the processor tests**

```python
# tests/test_processor.py
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.services.processor.processor import ProcessorService


def test_tick_processes_pending_item():
    mock_db = MagicMock()
    mock_item = MagicMock()
    mock_item.id = "item-1"
    mock_item.source_type = "gmail"
    mock_item.source_id = "msg-123"
    mock_item.raw_payload = {"from": "test@test.com", "subject": "Test", "body": "Hello", "headers": {}}
    mock_item.status = "pending"
    mock_item.claimed_at = None

    # Mock the query for pending items
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_item]

    classification = MagicMock()
    classification.is_knowledge = False
    classification.is_workflow_trigger = False
    classification.is_alert = False
    classification.summary = "Test email"

    with patch("app.services.processor.processor.should_filter", return_value=None), \
         patch("app.services.processor.processor.classify_item", return_value=classification), \
         patch("app.services.processor.processor.knowledge_handler") as mock_kh, \
         patch("app.services.processor.processor.workflow_handler") as mock_wh, \
         patch("app.services.processor.processor.alert_handler") as mock_ah:

        mock_kh.handle.return_value = None
        mock_wh.handle.return_value = None
        mock_ah.handle.return_value = None

        service = ProcessorService(mock_db)
        result = service.tick()

    assert result["processed"] == 1
    assert result["filtered"] == 0


def test_tick_filters_noise():
    mock_db = MagicMock()
    mock_item = MagicMock()
    mock_item.id = "item-1"
    mock_item.source_type = "gmail"
    mock_item.source_id = "msg-123"
    mock_item.raw_payload = {"from": "noreply@spam.com", "headers": {"List-Unsubscribe": "yes"}}
    mock_item.status = "pending"
    mock_item.claimed_at = None

    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_item]

    from app.services.processor.prefilter import FilterReason

    with patch("app.services.processor.processor.should_filter", return_value=FilterReason("newsletter_unsubscribe", "Has unsubscribe")):
        service = ProcessorService(mock_db)
        result = service.tick()

    assert result["filtered"] == 1
    assert result["processed"] == 0


def test_tick_skips_claimed_items():
    mock_db = MagicMock()
    mock_item = MagicMock()
    mock_item.id = "item-1"
    mock_item.source_type = "gmail"
    mock_item.status = "pending"
    mock_item.claimed_at = datetime.now(timezone.utc)  # Recently claimed
    mock_item.claimed_by = "other-worker"

    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_item]

    service = ProcessorService(mock_db)
    result = service.tick()

    assert result["processed"] == 0
    assert result["skipped"] == 1


def test_tick_empty_queue():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    service = ProcessorService(mock_db)
    result = service.tick()

    assert result["processed"] == 0
    assert result["filtered"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_processor.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the processor service**

```python
# app/services/processor/processor.py
"""Main processor service. Polls ingestion_queue, classifies, routes to handlers."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.ingestion import IngestionQueueItem, IngestionStatus
from app.services.processor.prefilter import should_filter
from app.services.processor.classifier import classify_item
from app.services.processor.handlers import knowledge as knowledge_handler
from app.services.processor.handlers import workflow as workflow_handler
from app.services.processor.handlers import alert as alert_handler

logger = logging.getLogger(__name__)

CLAIM_TIMEOUT = timedelta(minutes=15)
BATCH_LIMIT = 20


class ProcessorService:
    def __init__(self, db: Session, *, worker_name: str = "processor"):
        self.db = db
        self.worker_name = worker_name

    def tick(self, now: datetime | None = None) -> dict[str, int]:
        """Process one batch of pending items. Returns counts."""
        now = now or datetime.now(timezone.utc)
        counts = {"processed": 0, "filtered": 0, "failed": 0, "skipped": 0}

        items = (
            self.db.query(IngestionQueueItem)
            .filter(IngestionQueueItem.status == IngestionStatus.PENDING.value)
            .order_by(IngestionQueueItem.created_at.asc())
            .limit(BATCH_LIMIT)
            .all()
        )

        for item in items:
            # Check claim lock
            if item.claimed_at and item.claimed_at > now - CLAIM_TIMEOUT:
                counts["skipped"] += 1
                continue

            # Claim the item
            item.claimed_at = now
            item.claimed_by = self.worker_name
            item.status = IngestionStatus.PROCESSING.value
            self.db.flush()

            try:
                self._process_item(item, now)
                counts["processed" if item.status == IngestionStatus.COMPLETED.value else "filtered"] += 1
            except Exception:
                logger.exception("Failed to process item %s", item.id)
                item.status = IngestionStatus.FAILED.value
                item.error = "Processing failed — check logs"
                item.processed_at = now
                counts["failed"] += 1

        return counts

    def _process_item(self, item: IngestionQueueItem, now: datetime) -> None:
        """Run pre-filter, classifier, and handlers on a single item."""

        # Stage 1: Pre-filter
        filter_result = should_filter(item.source_type, item.raw_payload)
        if filter_result is not None:
            item.status = IngestionStatus.FILTERED.value
            item.result = {"filter_reason": filter_result.reason, "filter_detail": filter_result.detail}
            item.processed_at = now
            logger.info("Filtered item %s: %s", item.id, filter_result.reason)
            return

        # Stage 2: Classify via LLM
        active_workflows = self._get_active_workflows()
        entity_types = self._get_entity_types()

        classification = classify_item(
            source_type=item.source_type,
            raw_payload=item.raw_payload,
            active_workflows=active_workflows,
            entity_types=entity_types,
        )

        item.classification = {
            "summary": classification.summary,
            "is_knowledge": classification.is_knowledge,
            "knowledge_entities": classification.knowledge_entities,
            "is_workflow_trigger": classification.is_workflow_trigger,
            "workflow_slugs": classification.workflow_slugs,
            "workflow_reason": classification.workflow_reason,
            "is_alert": classification.is_alert,
            "alert_reason": classification.alert_reason,
        }

        # Stage 3: Route to handlers
        results = {}

        knowledge_result = knowledge_handler.handle(
            db=self.db,
            raw_payload=item.raw_payload,
            classification=classification,
        )
        if knowledge_result:
            results["knowledge"] = knowledge_result.detail

        workflow_result = workflow_handler.handle(
            db=self.db,
            raw_payload=item.raw_payload,
            classification=classification,
        )
        if workflow_result:
            results["workflow"] = workflow_result.detail

        alert_result = alert_handler.handle(
            raw_payload=item.raw_payload,
            classification=classification,
        )
        if alert_result:
            results["alert"] = alert_result.detail

        item.result = results
        item.status = IngestionStatus.COMPLETED.value
        item.processed_at = now
        logger.info("Processed item %s: %s", item.id, classification.summary)

    def _get_active_workflows(self) -> list[dict]:
        """Get list of active workflows for the classifier prompt."""
        from app.services.brain_query import BrainQuery
        bq = BrainQuery(self.db)
        workflows = bq.list_entities_by_type("workflow")
        return [
            {
                "slug": w.slug,
                "name": w.canonical_name,
                "description": w.description or "",
            }
            for w in workflows
        ]

    def _get_entity_types(self) -> list[str]:
        """Get distinct entity types from the graph."""
        from app.models.brain import EntityNode
        rows = (
            self.db.query(EntityNode.entity_type)
            .distinct()
            .all()
        )
        return [r[0] for r in rows]


def run_processor_loop(db_factory, *, interval_seconds: int = 5) -> None:
    """Main loop for the ntangible-processor systemd service."""
    logger.info("Processor loop starting (interval=%ds)", interval_seconds)
    while True:
        db = db_factory()
        try:
            service = ProcessorService(db)
            result = service.tick()
            db.commit()
            if any(result.values()):
                logger.info("Processor tick: %s", result)
        except Exception:
            logger.exception("Processor tick failed")
            db.rollback()
        finally:
            db.close()
        time.sleep(interval_seconds)
```

- [ ] **Step 4: Create the processor entrypoint script**

```python
# scripts/run_processor.py
"""Entrypoint for the ntangible-processor systemd service."""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.services.processor.processor import run_processor_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

if __name__ == "__main__":
    run_processor_loop(SessionLocal)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_processor.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/processor/processor.py scripts/run_processor.py tests/test_processor.py
git commit -m "feat: add main processor service with poll/claim/route loop"
```

---

### Task 8: Webhook Endpoints (Gmail + Calendar)

**Files:**
- Create: `app/api/webhook_routes.py`
- Modify: `app/main.py`
- Test: `tests/test_webhook_routes.py`

- [ ] **Step 1: Write the webhook route tests**

```python
# tests/test_webhook_routes.py
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


def _make_app():
    """Create a minimal app with webhook routes for testing."""
    from fastapi import FastAPI
    from app.api.webhook_routes import router
    app = FastAPI()
    app.include_router(router)
    return app


def test_gmail_webhook_enqueues_item():
    app = _make_app()
    client = TestClient(app)

    gmail_push = {
        "message": {
            "data": "eyJlbWFpbEFkZHJlc3MiOiJ0ZXN0QHRlc3QuY29tIiwiaGlzdG9yeUlkIjoiMTIzNDUifQ==",
            "messageId": "msg-001",
        },
        "subscription": "projects/test/subscriptions/gmail-push",
    }

    with patch("app.api.webhook_routes.fetch_and_enqueue_gmail") as mock_fetch:
        mock_fetch.return_value = {"queued": True}
        response = client.post("/webhooks/gmail", json=gmail_push)

    assert response.status_code == 200
    mock_fetch.assert_called_once()


def test_calendar_webhook_enqueues_item():
    app = _make_app()
    client = TestClient(app)

    with patch("app.api.webhook_routes.fetch_and_enqueue_calendar") as mock_fetch:
        mock_fetch.return_value = {"queued": True}
        response = client.post(
            "/webhooks/calendar",
            headers={
                "X-Goog-Channel-ID": "channel-123",
                "X-Goog-Resource-State": "exists",
            },
        )

    assert response.status_code == 200
    mock_fetch.assert_called_once()


def test_gmail_webhook_returns_200_on_error():
    """Google retries on non-200, so always return 200."""
    app = _make_app()
    client = TestClient(app)

    with patch("app.api.webhook_routes.fetch_and_enqueue_gmail", side_effect=Exception("boom")):
        response = client.post("/webhooks/gmail", json={"message": {"data": "dGVzdA==", "messageId": "x"}})

    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_webhook_routes.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement webhook routes**

```python
# app/api/webhook_routes.py
"""Webhook endpoints for Gmail and Google Calendar push notifications."""

from __future__ import annotations

import base64
import json
import logging

from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


def fetch_and_enqueue_gmail(push_data: dict) -> dict:
    """Fetch the email via Gmail API and write to ingestion_queue.

    This is a placeholder that will be fully implemented when
    the Gmail OAuth integration is built in the settings UI task.
    """
    from app.database import SessionLocal
    from app.models.ingestion import IngestionQueueItem, IngestionSourceType

    history_id = push_data.get("historyId", "unknown")
    email_address = push_data.get("emailAddress", "unknown")

    db = SessionLocal()
    try:
        item = IngestionQueueItem(
            source_type=IngestionSourceType.GMAIL.value,
            source_id=f"gmail-history-{history_id}",
            raw_payload={
                "history_id": history_id,
                "email_address": email_address,
                "status": "pending_fetch",
            },
        )
        db.add(item)
        db.commit()
        logger.info("Enqueued Gmail push: history_id=%s", history_id)
        return {"queued": True, "history_id": history_id}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def fetch_and_enqueue_calendar(channel_id: str, resource_state: str) -> dict:
    """Fetch changed calendar events and write to ingestion_queue.

    This is a placeholder that will be fully implemented when
    the Calendar OAuth integration is built in the settings UI task.
    """
    from app.database import SessionLocal
    from app.models.ingestion import IngestionQueueItem, IngestionSourceType

    db = SessionLocal()
    try:
        item = IngestionQueueItem(
            source_type=IngestionSourceType.CALENDAR.value,
            source_id=f"cal-{channel_id}-{resource_state}",
            raw_payload={
                "channel_id": channel_id,
                "resource_state": resource_state,
                "status": "pending_fetch",
            },
        )
        db.add(item)
        db.commit()
        logger.info("Enqueued Calendar push: channel=%s state=%s", channel_id, resource_state)
        return {"queued": True}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/webhooks/gmail")
async def gmail_webhook(request: Request) -> Response:
    """Receive Gmail push notifications via Google Pub/Sub."""
    try:
        body = await request.json()
        message = body.get("message", {})
        data_b64 = message.get("data", "")
        push_data = json.loads(base64.b64decode(data_b64).decode("utf-8"))
        fetch_and_enqueue_gmail(push_data)
    except Exception:
        logger.exception("Gmail webhook processing failed")
    # Always return 200 — Google retries on non-200
    return Response(status_code=200)


@router.post("/webhooks/calendar")
async def calendar_webhook(request: Request) -> Response:
    """Receive Google Calendar push notifications."""
    try:
        channel_id = request.headers.get("X-Goog-Channel-ID", "")
        resource_state = request.headers.get("X-Goog-Resource-State", "")
        if resource_state == "sync":
            # Initial sync confirmation — ignore
            return Response(status_code=200)
        fetch_and_enqueue_calendar(channel_id, resource_state)
    except Exception:
        logger.exception("Calendar webhook processing failed")
    return Response(status_code=200)
```

- [ ] **Step 4: Register webhook routes in main.py**

In `app/main.py`, add after the `mcp_router` import (around line 100):

```python
from app.api.webhook_routes import router as webhook_router
```

And add after `app.include_router(mcp_router)` (around line 121):

```python
app.include_router(webhook_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_webhook_routes.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/api/webhook_routes.py app/main.py tests/test_webhook_routes.py
git commit -m "feat: add Gmail and Calendar webhook endpoints"
```

---

### Task 9: MCP process_file Tool

**Files:**
- Modify: `ntangible_mcp/server.py`
- Modify: `ntangible_mcp/client.py`
- Test: `tests/test_mcp_process_file.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_mcp_process_file.py
import hashlib
from unittest.mock import patch, MagicMock

from ntangible_mcp.server import process_file


def test_process_file_calls_api():
    mock_client = MagicMock()
    mock_client.post.return_value = {"queued": True, "item_id": "abc-123"}

    with patch("ntangible_mcp.server._get_client", return_value=mock_client):
        result = process_file(
            file_content="This is a test document about marketing strategy.",
            file_name="strategy.txt",
        )

    assert "queued" in result
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/api/mcp/process-file"
    body = call_args[1].get("json") or call_args[0][1]
    assert body["file_name"] == "strategy.txt"
    assert "marketing strategy" in body["content"]


def test_process_file_with_type():
    mock_client = MagicMock()
    mock_client.post.return_value = {"queued": True}

    with patch("ntangible_mcp.server._get_client", return_value=mock_client):
        result = process_file(
            file_content="PDF content here",
            file_name="report.pdf",
            file_type="application/pdf",
        )

    call_args = mock_client.post.call_args
    body = call_args[1].get("json") or call_args[0][1]
    assert body["file_type"] == "application/pdf"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_mcp_process_file.py -v`
Expected: FAIL with `ImportError` (process_file not found)

- [ ] **Step 3: Add post method to MCP client**

In `ntangible_mcp/client.py`, add a `post` method to the `AppClient` class (after the existing `get` method):

```python
    def post(self, path: str, json: dict | None = None) -> dict:
        resp = self._client.post(path, json=json)
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: Add process_file tool to MCP server**

In `ntangible_mcp/server.py`, add the new tool after the existing tool definitions:

```python
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
    body = {
        "content": file_content,
        "file_name": file_name,
    }
    if file_type:
        body["file_type"] = file_type
    return _fmt(client.post("/api/mcp/process-file", json=body))
```

- [ ] **Step 5: Add the API endpoint for MCP file processing**

In `app/api/mcp_routes.py`, add at the bottom of the file:

```python
@router.post("/process-file")
def mcp_process_file(
    request_body: dict,
    db: Session = Depends(get_db),
):
    """Receive a file from the MCP and enqueue for processing."""
    import hashlib
    from app.models.ingestion import IngestionQueueItem, IngestionSourceType

    content = request_body.get("content", "")
    file_name = request_body.get("file_name", "unknown")
    file_type = request_body.get("file_type")

    source_id = hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]

    item = IngestionQueueItem(
        source_type=IngestionSourceType.MCP_FILE.value,
        source_id=f"mcp-{source_id}",
        raw_payload={
            "content": content,
            "file_name": file_name,
            "file_type": file_type,
        },
    )
    db.add(item)
    db.commit()

    return {"queued": True, "item_id": str(item.id)}
```

Also ensure `get_db` is imported at the top of `mcp_routes.py`. Check if it already is — if not, add:

```python
from app.database import get_db
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_mcp_process_file.py -v`
Expected: All 2 tests PASS

- [ ] **Step 7: Commit**

```bash
git add ntangible_mcp/server.py ntangible_mcp/client.py app/api/mcp_routes.py tests/test_mcp_process_file.py
git commit -m "feat: add process_file MCP tool and API endpoint"
```

---

### Task 10: Brain Settings Page (UI)

**Files:**
- Create: `app/web/brain_settings.py`
- Create: `app/web/templates/brain/settings.html`
- Modify: `app/main.py`
- Modify: `app/web/templates/base.html`

- [ ] **Step 1: Create the settings route module**

```python
# app/web/brain_settings.py
"""Brain Settings page — manage intake connections and view processing activity."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ingestion import IngestionQueueItem
from app.models.publishing_connection import AppConnection, ConnectionChannel, ConnectionStatus

logger = logging.getLogger(__name__)

try:
    from fastapi.templating import Jinja2Templates
except ImportError:
    Jinja2Templates = None

templates = (
    Jinja2Templates(directory="app/web/templates")
    if Jinja2Templates is not None
    else None
)

brain_settings_router = APIRouter(prefix="/control-room/brain", tags=["brain-settings"])


@brain_settings_router.get("/settings", response_class=HTMLResponse)
def brain_settings_page(request: Request, db: Session = Depends(get_db)):
    """Render the Brain Settings page."""
    # Get connection status for each intake channel
    connections = {}
    for channel in [ConnectionChannel.GMAIL, ConnectionChannel.CALENDAR, ConnectionChannel.TELEGRAM]:
        conn = db.query(AppConnection).filter(AppConnection.channel == channel).first()
        connections[channel.value] = {
            "status": conn.status.value if conn else "disconnected",
            "label": conn.connection_label if conn else None,
        }

    # Get processing queue stats
    now = datetime.now(timezone.utc)
    total_today = (
        db.query(IngestionQueueItem)
        .filter(IngestionQueueItem.created_at >= now.replace(hour=0, minute=0, second=0))
        .count()
    )
    pending = (
        db.query(IngestionQueueItem)
        .filter(IngestionQueueItem.status == "pending")
        .count()
    )
    errors = (
        db.query(IngestionQueueItem)
        .filter(IngestionQueueItem.status == "failed")
        .filter(IngestionQueueItem.created_at >= now.replace(hour=0, minute=0, second=0))
        .count()
    )

    # Recent activity
    recent = (
        db.query(IngestionQueueItem)
        .filter(IngestionQueueItem.status.in_(["completed", "filtered"]))
        .order_by(IngestionQueueItem.processed_at.desc())
        .limit(20)
        .all()
    )

    context = {
        "request": request,
        "connections": connections,
        "queue_stats": {
            "total_today": total_today,
            "pending": pending,
            "errors": errors,
        },
        "recent_activity": recent,
    }

    return templates.TemplateResponse(request, "brain/settings.html", context)
```

- [ ] **Step 2: Create the settings template**

```html
<!-- app/web/templates/brain/settings.html -->
{% extends "base.html" %}

{% block content %}
<div class="page-header">
    <h1>Brain Settings</h1>
    <p class="subtitle">Manage intake connections and monitor processing activity.</p>
</div>

<section class="card" style="margin-bottom: 1.5rem;">
    <h2>Intake Connections</h2>
    <p class="subtitle">Connect accounts to automatically process incoming data.</p>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; margin-top: 1rem;">
        <!-- Gmail -->
        <div class="card" style="padding: 1.25rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                <span style="font-size: 1.5rem;">&#x2709;</span>
                <div>
                    <strong>Gmail</strong>
                    {% if connections.gmail.status == 'connected' %}
                        <div class="badge badge--success" style="margin-left: 0.5rem;">Connected</div>
                    {% endif %}
                </div>
            </div>
            {% if connections.gmail.status == 'connected' %}
                <p style="color: var(--text-secondary); font-size: 0.875rem;">{{ connections.gmail.label }}</p>
                <button class="btn btn--outline btn--sm" disabled>Disconnect</button>
            {% else %}
                <p style="color: var(--text-secondary); font-size: 0.875rem;">Not connected</p>
                <button class="btn btn--primary btn--sm" disabled title="Google OAuth setup required">Connect</button>
            {% endif %}
        </div>

        <!-- Google Calendar -->
        <div class="card" style="padding: 1.25rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                <span style="font-size: 1.5rem;">&#x1F4C5;</span>
                <div>
                    <strong>Google Calendar</strong>
                    {% if connections.calendar.status == 'connected' %}
                        <div class="badge badge--success" style="margin-left: 0.5rem;">Connected</div>
                    {% endif %}
                </div>
            </div>
            {% if connections.calendar.status == 'connected' %}
                <p style="color: var(--text-secondary); font-size: 0.875rem;">{{ connections.calendar.label }}</p>
                <button class="btn btn--outline btn--sm" disabled>Disconnect</button>
            {% else %}
                <p style="color: var(--text-secondary); font-size: 0.875rem;">Not connected</p>
                <button class="btn btn--primary btn--sm" disabled title="Google OAuth setup required">Connect</button>
            {% endif %}
        </div>
    </div>
</section>

<section class="card" style="margin-bottom: 1.5rem;">
    <h2>Alert Channels</h2>
    <p class="subtitle">Configure where to send important notifications.</p>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; margin-top: 1rem;">
        <!-- Telegram -->
        <div class="card" style="padding: 1.25rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                <span style="font-size: 1.5rem;">&#x1F4AC;</span>
                <strong>Telegram</strong>
            </div>
            <p style="color: var(--text-secondary); font-size: 0.875rem;">Not connected</p>
            <button class="btn btn--primary btn--sm" disabled title="Coming soon">Connect</button>
        </div>

        <!-- WhatsApp -->
        <div class="card" style="padding: 1.25rem; opacity: 0.6;">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                <span style="font-size: 1.5rem;">&#x1F4AC;</span>
                <strong>WhatsApp</strong>
            </div>
            <p style="color: var(--text-secondary); font-size: 0.875rem;">Coming soon</p>
        </div>

        <!-- Slack -->
        <div class="card" style="padding: 1.25rem; opacity: 0.6;">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                <span style="font-size: 1.5rem;">&#x1F4AC;</span>
                <strong>Slack</strong>
            </div>
            <p style="color: var(--text-secondary); font-size: 0.875rem;">Coming soon</p>
        </div>
    </div>
</section>

<section class="card" style="margin-bottom: 1.5rem;">
    <h2>Processing Queue</h2>
    <div style="display: flex; gap: 2rem; margin-top: 1rem;">
        <div>
            <div style="font-size: 2rem; font-weight: 600;">{{ queue_stats.total_today }}</div>
            <div style="color: var(--text-secondary); font-size: 0.875rem;">Processed today</div>
        </div>
        <div>
            <div style="font-size: 2rem; font-weight: 600;">{{ queue_stats.pending }}</div>
            <div style="color: var(--text-secondary); font-size: 0.875rem;">Pending</div>
        </div>
        <div>
            <div style="font-size: 2rem; font-weight: 600; {% if queue_stats.errors > 0 %}color: var(--danger);{% endif %}">{{ queue_stats.errors }}</div>
            <div style="color: var(--text-secondary); font-size: 0.875rem;">Errors</div>
        </div>
    </div>
</section>

<section class="card">
    <h2>Recent Activity</h2>
    {% if recent_activity %}
    <table class="table" style="margin-top: 1rem;">
        <thead>
            <tr>
                <th>Time</th>
                <th>Source</th>
                <th>Summary</th>
                <th>Handlers</th>
            </tr>
        </thead>
        <tbody>
            {% for item in recent_activity %}
            <tr>
                <td style="white-space: nowrap;">{{ item.processed_at.strftime('%H:%M') if item.processed_at else '—' }}</td>
                <td>{{ item.source_type }}</td>
                <td>{{ item.classification.summary if item.classification else item.result.get('filter_reason', '—') if item.result else '—' }}</td>
                <td>
                    {% if item.result %}
                        {% if 'knowledge' in item.result %}<span class="badge">Knowledge</span>{% endif %}
                        {% if 'workflow' in item.result %}<span class="badge">Workflow</span>{% endif %}
                        {% if 'alert' in item.result %}<span class="badge">Alert</span>{% endif %}
                        {% if 'filter_reason' in item.result %}<span class="badge badge--muted">Filtered</span>{% endif %}
                    {% else %}
                        —
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <p style="color: var(--text-secondary); margin-top: 1rem;">No items processed yet.</p>
    {% endif %}
</section>
{% endblock %}
```

- [ ] **Step 3: Register the brain settings routes in main.py**

In `app/main.py`, add the import after the web router imports (inside the `try` block around line 125):

```python
    from app.web.brain_settings import brain_settings_router
```

And add the include after the other web router includes (around line 138):

```python
    app.include_router(brain_settings_router)
```

- [ ] **Step 4: Add Settings link to brain sidebar in base.html**

In `app/web/templates/base.html`, find the brain sidebar navigation section that contains links like "Overview", "Graph", "Knowledge", etc. Add after the last brain nav item (e.g., after "Topics"):

```html
<li><a href="/control-room/brain/settings">Settings</a></li>
```

Look for the pattern — it will be a `<ul>` or `<nav>` with the brain navigation links. Add the Settings link at the bottom of that list.

- [ ] **Step 5: Test manually by starting the dev server**

Run: `.venv/bin/python -m uvicorn app.main:app --reload`
Navigate to: `http://localhost:8000/control-room/brain/settings`
Expected: Settings page renders with connection cards, queue stats, and empty activity table

- [ ] **Step 6: Commit**

```bash
git add app/web/brain_settings.py app/web/templates/brain/settings.html app/main.py app/web/templates/base.html
git commit -m "feat: add Brain Settings page with connections and processing queue"
```

---

### Task 11: Deploy to Production

**Files:**
- No new files — deployment of all previous tasks

- [ ] **Step 1: Run the full test suite locally**

Run: `.venv/bin/pytest tests/test_ingestion_model.py tests/test_prefilter.py tests/test_classifier.py tests/test_alert_handler.py tests/test_workflow_handler.py tests/test_knowledge_handler.py tests/test_processor.py tests/test_webhook_routes.py tests/test_mcp_process_file.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run the migration on production**

```bash
ssh -i /tmp/lightsail_key.pem ubuntu@3.21.155.208 "cd /home/ubuntu/app && .venv/bin/alembic upgrade head"
```

Expected: Migration applies successfully, `ingestion_queue` table created, enum values added.

- [ ] **Step 3: Deploy the code to production**

Push to trigger the GitHub Actions deploy:

```bash
git push origin partner-engine-all
```

Or manually SCP and restart if the deploy workflow isn't working:

```bash
scp -i /tmp/lightsail_key.pem -r app/services/processor app/models/ingestion.py app/api/webhook_routes.py app/web/brain_settings.py app/web/templates/brain/ app/main.py app/config.py app/models/publishing_connection.py scripts/run_processor.py ntangible_mcp/server.py ntangible_mcp/client.py ubuntu@3.21.155.208:/home/ubuntu/app/
ssh -i /tmp/lightsail_key.pem ubuntu@3.21.155.208 "sudo systemctl restart ntangible-web"
```

- [ ] **Step 4: Create the processor systemd service**

```bash
ssh -i /tmp/lightsail_key.pem ubuntu@3.21.155.208 "sudo tee /etc/systemd/system/ntangible-processor.service > /dev/null << 'EOF'
[Unit]
Description=NTangible Marketing Processor
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/app
ExecStart=/home/ubuntu/app/.venv/bin/python scripts/run_processor.py
Restart=always
RestartSec=5
Environment=PYTHONPATH=/home/ubuntu/app

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable ntangible-processor
sudo systemctl start ntangible-processor
sudo systemctl status ntangible-processor --no-pager"
```

Expected: Service starts and shows `active (running)`

- [ ] **Step 5: Verify the settings page on production**

Navigate to: `https://3-21-155-208.nip.io/control-room/brain/settings`
Expected: Settings page renders with all connection cards and empty processing queue

- [ ] **Step 6: Commit any deployment fixes**

If any fixes were needed during deployment, commit them:

```bash
git add -A
git commit -m "fix: deployment adjustments for processing agent"
```
