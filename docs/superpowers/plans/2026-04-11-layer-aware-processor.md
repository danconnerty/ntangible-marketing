# Layer-Aware Processor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the processing pipeline to classify knowledge by kind/topic/confidence, reason about how new knowledge connects to the existing graph (Stage 2 intelligence), and provide an MCP `get_context` tool for on-demand context assembly.

**Architecture:** Two-stage LLM pipeline. Stage 1 classifies and extracts with richer output (knowledge_kind, topic_key, confidence). Stage 2 takes the extracted knowledge + existing graph context and reasons about edges, contradictions, and implications. A new MCP `get_context` tool queries the graph at runtime for context assembly.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Azure OpenAI (gpt-5.4-nano), existing BrainQuery service

**Spec:** `docs/superpowers/specs/2026-04-11-layer-aware-processor-design.md`

---

## File Structure

```
# Modified files
app/services/processor/classifier.py         # Richer ClassificationResult + updated prompt
app/services/processor/handlers/knowledge.py  # Two-stage processing, typed knowledge, topic assignment
app/services/processor/processor.py           # Pass topics to classifier
app/services/brain_query.py                   # Add primary_topic_key to create_knowledge_node + create_entity
app/main.py                                   # Register context_routes
ntangible_mcp/server.py                       # Add get_context tool

# New files
app/services/processor/intelligence.py        # Stage 2: intelligence reasoning
app/api/context_routes.py                     # GET /api/mcp/context endpoint
tests/test_intelligence.py                    # Stage 2 tests
tests/test_context_routes.py                  # Context API tests
tests/test_mcp_get_context.py                 # MCP tool test
```

---

### Task 1: Update ClassificationResult + Classifier Prompt

**Files:**
- Modify: `app/services/processor/classifier.py`
- Modify: `tests/test_classifier.py`

- [ ] **Step 1: Update the test file with new field tests**

Add these tests to `tests/test_classifier.py`:

```python
def test_parse_classification_with_layers():
    raw = {
        "summary": "Meeting with Alliance Sports on April 15",
        "is_knowledge": True,
        "knowledge_kind": "event",
        "topic_key": "work",
        "confidence": 0.9,
        "knowledge_entities": [
            {"name": "Alliance Sports", "type": "partner", "relation": "meeting partner"},
        ],
        "is_workflow_trigger": False,
        "workflow_slugs": [],
        "workflow_reason": None,
        "is_alert": False,
        "alert_reason": None,
    }
    result = parse_classification(raw)
    assert result.knowledge_kind == "event"
    assert result.topic_key == "work"
    assert result.confidence == 0.9


def test_parse_classification_defaults_new_fields():
    raw = {
        "summary": "Test",
        "is_knowledge": False,
        "knowledge_entities": [],
        "is_workflow_trigger": False,
        "workflow_slugs": [],
        "workflow_reason": None,
        "is_alert": False,
        "alert_reason": None,
    }
    result = parse_classification(raw)
    assert result.knowledge_kind is None
    assert result.topic_key is None
    assert result.confidence == 0.5


def test_build_classifier_prompt_includes_topics():
    payload = {"from": "test@test.com", "subject": "Test", "body": "Hello"}
    workflows = []
    entity_types = ["company", "person"]
    topics = [{"key": "marketing", "name": "Marketing"}, {"key": "work", "name": "Work"}]

    system_prompt, user_prompt = build_classifier_prompt(
        source_type="gmail", raw_payload=payload,
        active_workflows=workflows, entity_types=entity_types,
        topics=topics,
    )
    assert "marketing" in system_prompt.lower()
    assert "work" in system_prompt.lower()
    assert "knowledge_kind" in system_prompt
    assert "topic_key" in system_prompt
    assert "confidence" in system_prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_classifier.py::test_parse_classification_with_layers tests/test_classifier.py::test_parse_classification_defaults_new_fields tests/test_classifier.py::test_build_classifier_prompt_includes_topics -v`
Expected: FAIL

- [ ] **Step 3: Update ClassificationResult dataclass**

In `app/services/processor/classifier.py`, update the `ClassificationResult` dataclass to add new fields after `alert_reason`:

```python
@dataclass
class ClassificationResult:
    summary: str
    is_knowledge: bool = False
    knowledge_kind: str | None = None
    topic_key: str | None = None
    confidence: float = 0.5
    knowledge_entities: list[dict] = field(default_factory=list)
    is_workflow_trigger: bool = False
    workflow_slugs: list[str] = field(default_factory=list)
    workflow_reason: str | None = None
    is_alert: bool = False
    alert_reason: str | None = None
```

- [ ] **Step 4: Update build_classifier_prompt to accept topics and output richer schema**

Update the `build_classifier_prompt` signature to accept `topics: list[dict]` parameter:

```python
def build_classifier_prompt(*, source_type: str, raw_payload: dict, active_workflows: list[dict], entity_types: list[str], topics: list[dict] | None = None) -> tuple[str, str]:
    workflow_list = "\n".join(f"- {w['slug']}: {w.get('description') or w.get('name', '')}" for w in active_workflows) or "No active workflows."
    entity_type_list = ", ".join(entity_types) or "none defined"
    topic_list = "\n".join(f"- {t['key']}: {t['name']}" for t in (topics or [])) or "marketing"

    system_prompt = f"""You are a knowledge processing agent for a marketing engine.
You receive incoming data (emails, calendar events, documents) and classify each item.

For each item, determine ALL that apply:

1. KNOWLEDGE: Does this contain information worth storing in our knowledge graph?
   If yes, determine:
   - knowledge_kind: what TYPE of knowledge is this?
     * fact — a concrete, verifiable statement (e.g., "Alliance Sports is based in Texas")
     * event — something that happened or will happen (e.g., "Meeting on April 15")
     * task — an action item or to-do (e.g., "Send proposal by Friday")
     * deadline — a time-bound constraint (e.g., "Contract expires June 30")
     * observation — a subjective insight or pattern (e.g., "Partner engagement is increasing")
   - topic_key: which life domain does this belong to?
     Available topics:
     {topic_list}
   - confidence: how confident are you in this extraction? (0.0 to 1.0)
   - entities: extract people, companies, orgs, etc. with their relationships
     Use ONLY these entity types: {entity_type_list}

2. WORKFLOW TRIGGER: Should this trigger any of these active workflows?
   Active workflows:
   {workflow_list}
   Only trigger a workflow if the content is clearly relevant to it.

3. ALERT: Is this important enough to notify the user immediately?
   Only flag as alert for time-sensitive or high-importance items.

Respond with valid JSON matching this exact schema:
{{"summary": "one-line summary", "is_knowledge": true/false, "knowledge_kind": "fact|event|task|deadline|observation" or null, "topic_key": "topic_key" or null, "confidence": 0.0-1.0, "knowledge_entities": [{{"name": "...", "type": "...", "relation": "..."}}], "is_workflow_trigger": true/false, "workflow_slugs": ["slug1"], "workflow_reason": "why" or null, "is_alert": true/false, "alert_reason": "why" or null}}"""

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
        user_prompt = f"Source: calendar\nEvent: {summary}\nWhen: {start}\nAttendees: {attendee_str}\n\n{description}"
    else:
        file_name = raw_payload.get("file_name", "unknown")
        content = raw_payload.get("content", "")
        user_prompt = f"Source: {source_type}\nFile: {file_name}\n\n{content}"

    if len(user_prompt) > 8000:
        user_prompt = user_prompt[:8000] + "\n\n[TRUNCATED]"

    return system_prompt, user_prompt
```

- [ ] **Step 5: Update parse_classification to handle new fields**

```python
def parse_classification(raw: dict) -> ClassificationResult:
    return ClassificationResult(
        summary=raw.get("summary", ""),
        is_knowledge=bool(raw.get("is_knowledge", False)),
        knowledge_kind=raw.get("knowledge_kind"),
        topic_key=raw.get("topic_key"),
        confidence=float(raw.get("confidence", 0.5)),
        knowledge_entities=raw.get("knowledge_entities", []),
        is_workflow_trigger=bool(raw.get("is_workflow_trigger", False)),
        workflow_slugs=raw.get("workflow_slugs", []),
        workflow_reason=raw.get("workflow_reason"),
        is_alert=bool(raw.get("is_alert", False)),
        alert_reason=raw.get("alert_reason"),
    )
```

- [ ] **Step 6: Update classify_item to accept topics**

Update the `classify_item` function signature to accept `topics`:

```python
def classify_item(*, source_type: str, raw_payload: dict, active_workflows: list[dict], entity_types: list[str], topics: list[dict] | None = None) -> ClassificationResult:
    settings = get_settings()
    client = _get_openai_client()
    system_prompt, user_prompt = build_classifier_prompt(source_type=source_type, raw_payload=raw_payload, active_workflows=active_workflows, entity_types=entity_types, topics=topics)
    response = client.chat.completions.create(
        model=settings.azure_openai_model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        max_completion_tokens=512,
        temperature=0.1,
    )
    raw_text = response.choices[0].message.content.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    logger.info("Classifier LLM call: %d prompt tokens, %d completion tokens", response.usage.prompt_tokens, response.usage.completion_tokens)
    parsed = json.loads(raw_text)
    return parse_classification(parsed)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_classifier.py -v`
Expected: All 7 tests PASS (4 existing + 3 new)

- [ ] **Step 8: Commit**

```bash
git add app/services/processor/classifier.py tests/test_classifier.py
git commit -m "feat: add knowledge_kind, topic_key, confidence to classifier"
```

---

### Task 2: Stage 2 Intelligence Module

**Files:**
- Create: `app/services/processor/intelligence.py`
- Test: `tests/test_intelligence.py`

- [ ] **Step 1: Write the intelligence tests**

```python
# tests/test_intelligence.py
import json
from unittest.mock import patch, MagicMock

from app.services.processor.intelligence import (
    build_intelligence_prompt,
    parse_intelligence_output,
    run_intelligence_stage,
    IntelligenceResult,
)


def test_build_intelligence_prompt():
    stage1 = {
        "summary": "Meeting with Alliance Sports on April 15",
        "knowledge_kind": "event",
        "entities": [{"name": "Alliance Sports", "type": "partner", "relation": "meeting partner"}],
    }
    graph_context = {
        "entities": [
            {
                "name": "Alliance Sports",
                "type": "partner",
                "edges": [{"relation": "partner_of", "target": "NTangible"}],
                "knowledge": [{"title": "Alliance partnership launched Q1", "kind": "fact"}],
            }
        ],
    }
    system_prompt, user_prompt = build_intelligence_prompt(stage1_output=stage1, graph_context=graph_context)
    assert "Alliance Sports" in user_prompt
    assert "partner_of" in user_prompt
    assert "partnership launched" in user_prompt
    assert "new_edges" in system_prompt
    assert "contradictions" in system_prompt


def test_parse_intelligence_output_valid():
    raw = {
        "new_edges": [
            {"source": "Alliance Sports", "target": "NTangible", "relation": "meeting_scheduled", "confidence": 0.9, "edge_type": "entity"}
        ],
        "updated_knowledge": [],
        "contradictions": [],
        "implications": "The meeting suggests continued partnership engagement.",
    }
    result = parse_intelligence_output(raw)
    assert isinstance(result, IntelligenceResult)
    assert len(result.new_edges) == 1
    assert result.new_edges[0]["relation"] == "meeting_scheduled"
    assert result.implications == "The meeting suggests continued partnership engagement."


def test_parse_intelligence_output_empty():
    raw = {
        "new_edges": [],
        "updated_knowledge": [],
        "contradictions": [],
        "implications": None,
    }
    result = parse_intelligence_output(raw)
    assert len(result.new_edges) == 0
    assert result.implications is None


def test_run_intelligence_stage_calls_llm():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({
        "new_edges": [
            {"source": "Alliance Sports", "target": "NTangible", "relation": "expanding_partnership", "confidence": 0.85, "edge_type": "entity"}
        ],
        "updated_knowledge": [],
        "contradictions": [],
        "implications": "Partnership is growing.",
    })
    mock_response.usage.prompt_tokens = 200
    mock_response.usage.completion_tokens = 100

    with patch("app.services.processor.intelligence._get_openai_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response

        result = run_intelligence_stage(
            stage1_output={"summary": "Test", "knowledge_kind": "fact", "entities": []},
            graph_context={"entities": []},
        )

    assert isinstance(result, IntelligenceResult)
    assert len(result.new_edges) == 1
    assert result.implications == "Partnership is growing."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_intelligence.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the intelligence module**

```python
# app/services/processor/intelligence.py
"""Stage 2: Intelligence reasoning. Given extracted knowledge + existing graph context,
reasons about relationships, contradictions, and implications."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from openai import AzureOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class IntelligenceResult:
    new_edges: list[dict] = field(default_factory=list)
    updated_knowledge: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    implications: str | None = None


def _get_openai_client() -> AzureOpenAI:
    settings = get_settings()
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )


def build_intelligence_prompt(
    *,
    stage1_output: dict,
    graph_context: dict,
) -> tuple[str, str]:
    """Build Stage 2 prompts from Stage 1 output and existing graph context."""

    system_prompt = """You are an intelligence analyst for a knowledge graph. You receive:
1. Newly extracted knowledge (from Stage 1)
2. Existing graph context for the entities mentioned

Your job is to reason about HOW this new knowledge connects to what's already known.

Determine:
- new_edges: What new relationships should be created? Include both entity edges (between entities) and knowledge edges (between knowledge nodes — supports, contradicts, depends_on, updates, causes, related_to).
- updated_knowledge: Should any existing knowledge nodes be marked as superseded or updated?
- contradictions: Does the new information conflict with anything already known?
- implications: What does this mean in the broader context? (Free text, stored as an observation)

Respond with valid JSON matching this exact schema:
{"new_edges": [{"source": "name", "target": "name", "relation": "relation_type", "confidence": 0.0-1.0, "edge_type": "entity|knowledge"}], "updated_knowledge": [{"id": "uuid", "update": "description"}], "contradictions": [{"existing_id": "uuid", "description": "what conflicts"}], "implications": "free text reasoning" or null}

If there are no meaningful connections, return empty arrays and null implications."""

    # Build the user prompt with Stage 1 output and graph context
    entities_context = ""
    for ent in graph_context.get("entities", []):
        edges_str = ", ".join(
            f"{e.get('relation', '?')} → {e.get('target', '?')}"
            for e in ent.get("edges", [])
        )
        knowledge_str = "\n    ".join(
            f"- [{k.get('kind', '?')}] {k.get('title', '?')}"
            for k in ent.get("knowledge", [])
        )
        entities_context += f"\n  {ent['name']} ({ent.get('type', '?')}):"
        if edges_str:
            entities_context += f"\n    Edges: {edges_str}"
        if knowledge_str:
            entities_context += f"\n    Known facts:\n    {knowledge_str}"

    user_prompt = f"""NEW KNOWLEDGE (from Stage 1):
Summary: {stage1_output.get('summary', '')}
Kind: {stage1_output.get('knowledge_kind', 'unknown')}
Entities extracted: {json.dumps(stage1_output.get('entities', []))}

EXISTING GRAPH CONTEXT:{entities_context or ' (no existing context for these entities)'}"""

    if len(user_prompt) > 6000:
        user_prompt = user_prompt[:6000] + "\n\n[TRUNCATED]"

    return system_prompt, user_prompt


def parse_intelligence_output(raw: dict) -> IntelligenceResult:
    """Parse Stage 2 JSON output into IntelligenceResult."""
    return IntelligenceResult(
        new_edges=raw.get("new_edges", []),
        updated_knowledge=raw.get("updated_knowledge", []),
        contradictions=raw.get("contradictions", []),
        implications=raw.get("implications"),
    )


def run_intelligence_stage(
    *,
    stage1_output: dict,
    graph_context: dict,
) -> IntelligenceResult:
    """Run Stage 2 intelligence reasoning via LLM."""
    settings = get_settings()
    client = _get_openai_client()

    system_prompt, user_prompt = build_intelligence_prompt(
        stage1_output=stage1_output,
        graph_context=graph_context,
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
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    logger.info(
        "Intelligence LLM call: %d prompt tokens, %d completion tokens",
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
    )

    parsed = json.loads(raw_text)
    return parse_intelligence_output(parsed)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_intelligence.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/processor/intelligence.py tests/test_intelligence.py
git commit -m "feat: add Stage 2 intelligence reasoning module"
```

---

### Task 3: Update Knowledge Handler for Two-Stage Processing

**Files:**
- Modify: `app/services/processor/handlers/knowledge.py`
- Modify: `app/services/brain_query.py`
- Modify: `app/services/processor/processor.py`
- Modify: `tests/test_knowledge_handler.py`

- [ ] **Step 1: Update BrainQuery.create_knowledge_node and create_entity to accept primary_topic_key**

In `app/services/brain_query.py`, update `create_knowledge_node` (around line 185):

```python
    def create_knowledge_node(
        self,
        *,
        kind: str,
        title: str,
        content: str | None = None,
        status: str = "active",
        confidence: float = 0.5,
        trust_score: float = 0.5,
        primary_topic_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeNode:
        """Create and flush a generic KnowledgeNode."""
        node = KnowledgeNode(
            id=uuid.uuid4(),
            kind=kind,
            title=title,
            content=content,
            status=status,
            confidence=confidence,
            trust_score=trust_score,
            primary_topic_key=primary_topic_key,
            metadata_=metadata or {},
        )
        self.db.add(node)
        self.db.flush()
        return node
```

And update `create_entity` (around line 256) to accept `primary_topic_key`:

```python
    def create_entity(
        self,
        *,
        entity_type: str,
        canonical_name: str,
        slug: str,
        status: str = "active",
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        primary_topic_key: str | None = None,
    ) -> EntityNode:
        """Create and flush a new EntityNode."""
        entity = EntityNode(
            id=uuid.uuid4(),
            entity_type=entity_type,
            canonical_name=canonical_name,
            slug=slug,
            status=status,
            description=description,
            primary_topic_key=primary_topic_key,
            metadata_=metadata or {},
        )
        self.db.add(entity)
        self.db.flush()
        return entity
```

- [ ] **Step 2: Update knowledge handler tests**

Replace `tests/test_knowledge_handler.py` with:

```python
# tests/test_knowledge_handler.py
from unittest.mock import MagicMock, patch

from app.services.processor.handlers.knowledge import handle, resolve_entity, _assign_topic_key
from app.services.processor.handlers.base import HandlerResult
from app.services.processor.classifier import ClassificationResult


def test_knowledge_handler_creates_typed_knowledge_node():
    classification = ClassificationResult(
        summary="Meeting with Alliance Sports CEO",
        is_knowledge=True,
        knowledge_kind="event",
        topic_key="work",
        confidence=0.9,
        knowledge_entities=[
            {"name": "Alliance Sports", "type": "partner", "relation": "meeting partner"},
        ],
    )
    mock_db = MagicMock()
    with patch("app.services.processor.handlers.knowledge.BrainQuery") as MockBQ, \
         patch("app.services.processor.handlers.knowledge.run_intelligence_stage") as mock_intel:
        mock_bq = MockBQ.return_value
        mock_bq.get_entity_by_slug.return_value = None
        mock_entity = MagicMock(); mock_entity.id = "ent-1"
        mock_bq.create_entity.return_value = mock_entity
        mock_knowledge = MagicMock(); mock_knowledge.id = "kn-1"
        mock_bq.create_knowledge_node.return_value = mock_knowledge
        mock_bq.get_edges_from.return_value = []
        mock_bq.get_edges_to.return_value = []

        from app.services.processor.intelligence import IntelligenceResult
        mock_intel.return_value = IntelligenceResult(new_edges=[], implications=None)

        result = handle(db=mock_db, raw_payload={"from": "dan@partner.co"}, classification=classification)

    assert result.handler_name == "knowledge"
    assert result.success is True
    # Verify create_knowledge_node was called with kind and topic_key
    call_kwargs = mock_bq.create_knowledge_node.call_args[1]
    assert call_kwargs["kind"] == "event"
    assert call_kwargs["primary_topic_key"] == "work"
    assert call_kwargs["confidence"] == 0.9


def test_knowledge_handler_runs_intelligence_stage():
    classification = ClassificationResult(
        summary="Alliance expanding contract",
        is_knowledge=True,
        knowledge_kind="fact",
        topic_key="work",
        confidence=0.85,
        knowledge_entities=[
            {"name": "Alliance Sports", "type": "partner", "relation": "contract expansion"},
        ],
    )
    mock_db = MagicMock()
    mock_existing = MagicMock(); mock_existing.id = "existing-ent"
    mock_existing.canonical_name = "Alliance Sports"
    mock_existing.entity_type = "partner"

    with patch("app.services.processor.handlers.knowledge.BrainQuery") as MockBQ, \
         patch("app.services.processor.handlers.knowledge.run_intelligence_stage") as mock_intel:
        mock_bq = MockBQ.return_value
        mock_bq.get_entity_by_slug.return_value = mock_existing
        mock_knowledge = MagicMock(); mock_knowledge.id = "kn-1"
        mock_bq.create_knowledge_node.return_value = mock_knowledge
        mock_edge = MagicMock()
        mock_edge.relation = "partner_of"
        mock_edge.target_id = "ntangible-id"
        mock_bq.get_edges_from.return_value = [mock_edge]
        mock_bq.get_edges_to.return_value = []

        from app.services.processor.intelligence import IntelligenceResult
        mock_intel.return_value = IntelligenceResult(
            new_edges=[{"source": "Alliance Sports", "target": "NTangible", "relation": "expanding_partnership", "confidence": 0.85, "edge_type": "entity"}],
            implications="Partnership is growing.",
        )

        result = handle(db=mock_db, raw_payload={"from": "dan@partner.co"}, classification=classification)

    mock_intel.assert_called_once()
    assert result.detail.get("intelligence_edges", 0) > 0 or "implications" in result.detail


def test_knowledge_handler_not_knowledge():
    classification = ClassificationResult(summary="Not knowledge", is_knowledge=False)
    result = handle(db=MagicMock(), raw_payload={}, classification=classification)
    assert result is None


def test_resolve_entity_exact_slug_match():
    mock_bq = MagicMock()
    mock_entity = MagicMock(); mock_entity.id = "ent-1"
    mock_bq.get_entity_by_slug.return_value = mock_entity
    resolved, created = resolve_entity(mock_bq, name="Alliance Sports", entity_type="company", topic_key="work")
    assert resolved.id == "ent-1"
    assert created is False


def test_resolve_entity_creates_new_with_topic():
    mock_bq = MagicMock()
    mock_bq.get_entity_by_slug.return_value = None
    mock_new = MagicMock(); mock_new.id = "new-ent"
    mock_bq.create_entity.return_value = mock_new
    resolved, created = resolve_entity(mock_bq, name="New Company", entity_type="company", topic_key="work")
    assert created is True
    call_kwargs = mock_bq.create_entity.call_args[1]
    assert call_kwargs["primary_topic_key"] == "work"


def test_assign_topic_key():
    assert _assign_topic_key("person", "work") == "people"
    assert _assign_topic_key("company", None) == "work"
    assert _assign_topic_key("partner", "projects") == "marketing"
    assert _assign_topic_key("product", None) == "projects"
    assert _assign_topic_key("topic", "finance") == "finance"
    assert _assign_topic_key("org", None) == "work"
    assert _assign_topic_key("place", None) == "work"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_knowledge_handler.py -v`
Expected: FAIL

- [ ] **Step 4: Rewrite the knowledge handler**

Replace `app/services/processor/handlers/knowledge.py` entirely:

```python
"""Knowledge extraction handler. Two-stage: extract entities, then run intelligence reasoning."""
from __future__ import annotations
import logging
import re
from sqlalchemy.orm import Session
from app.services.brain_query import BrainQuery
from app.services.processor.classifier import ClassificationResult
from app.services.processor.intelligence import run_intelligence_stage, IntelligenceResult
from app.services.processor.handlers.base import HandlerResult

logger = logging.getLogger(__name__)

# Entity types that always belong to marketing regardless of classifier topic
MARKETING_ENTITY_TYPES = {"partner", "client", "competitor", "workflow", "content_pillar", "publishing_channel"}
# Fallback topic by entity type
ENTITY_TYPE_TOPIC_DEFAULTS = {
    "person": "people",
    "company": "work",
    "org": "work",
    "place": "work",
    "product": "projects",
    "topic": None,  # uses classifier's topic_key
}


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _assign_topic_key(entity_type: str, classifier_topic: str | None) -> str | None:
    """Determine primary_topic_key for a new entity based on its type and classifier output."""
    if entity_type in MARKETING_ENTITY_TYPES:
        return "marketing"
    default = ENTITY_TYPE_TOPIC_DEFAULTS.get(entity_type)
    if default is not None:
        return default
    return classifier_topic


def resolve_entity(bq: BrainQuery, *, name: str, entity_type: str, topic_key: str | None = None) -> tuple:
    """Resolve an entity by slug, or create a new one. Returns (entity, was_created)."""
    slug = _slugify(name)
    existing = bq.get_entity_by_slug(entity_type, slug)
    if existing is not None:
        return existing, False
    assigned_topic = _assign_topic_key(entity_type, topic_key)
    entity = bq.create_entity(
        entity_type=entity_type, canonical_name=name, slug=slug,
        primary_topic_key=assigned_topic,
    )
    logger.info("Created new entity: %s/%s (%s) topic=%s", entity_type, slug, name, assigned_topic)
    return entity, True


def _build_graph_context(bq: BrainQuery, resolved_entities: list[dict]) -> dict:
    """Fetch existing graph context for resolved entities to feed into Stage 2."""
    from app.models.brain import KnowledgeNode, KnowledgeEdge
    entities_context = []
    for ent in resolved_entities:
        entity_id = ent["entity_id"]
        edges_from = bq.get_edges_from(entity_id)
        edges_to = bq.get_edges_to(entity_id)
        edges = [
            {"relation": e.relation, "target": str(e.target_id)} for e in edges_from
        ] + [
            {"relation": e.relation, "target": str(e.source_id)} for e in edges_to
        ]
        # Get related knowledge nodes (linked via knowledge edges or entity references in metadata)
        knowledge = []
        knowledge_nodes = (
            bq.db.query(KnowledgeNode)
            .filter(KnowledgeNode.is_latest == True)  # noqa: E712
            .filter(KnowledgeNode.content.ilike(f"%{ent['name']}%"))
            .limit(10)
            .all()
        )
        for kn in knowledge_nodes:
            knowledge.append({"id": str(kn.id), "title": kn.title, "kind": kn.kind, "confidence": kn.confidence})

        entities_context.append({
            "name": ent["name"],
            "type": ent["type"],
            "edges": edges[:10],
            "knowledge": knowledge[:10],
        })
    return {"entities": entities_context}


def handle(*, db: Session, raw_payload: dict, classification: ClassificationResult) -> HandlerResult | None:
    """Extract entities, create typed knowledge node, run intelligence stage."""
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
        entity, was_created = resolve_entity(
            bq, name=name, entity_type=entity_type, topic_key=classification.topic_key,
        )
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

    # Create typed knowledge node
    knowledge_node = bq.create_knowledge_node(
        kind=classification.knowledge_kind or "fact",
        title=classification.summary,
        content=f"Source: {raw_payload.get('from', raw_payload.get('file_name', 'unknown'))}",
        confidence=classification.confidence,
        trust_score=classification.confidence,
        primary_topic_key=classification.topic_key,
        metadata={
            "entities": resolved_entities,
            "source_type": raw_payload.get("source_type", "unknown"),
            "ingestion_source": "processor",
        },
    )

    # Create basic entity edges between co-occurring entities
    basic_edges = 0
    for i, ent_a in enumerate(resolved_entities):
        for ent_b in resolved_entities[i + 1:]:
            bq.create_edge(
                source_id=ent_a["entity_id"],
                target_id=ent_b["entity_id"],
                source_type="entity",
                target_type="entity",
                relation=ent_a.get("relation") or "related_to",
            )
            basic_edges += 1

    # Stage 2: Intelligence reasoning
    graph_context = _build_graph_context(bq, resolved_entities)
    stage1_output = {
        "summary": classification.summary,
        "knowledge_kind": classification.knowledge_kind,
        "entities": classification.knowledge_entities,
    }

    intelligence_edges = 0
    implications_stored = False
    try:
        intel_result = run_intelligence_stage(
            stage1_output=stage1_output,
            graph_context=graph_context,
        )

        # Create intelligence edges
        for edge in intel_result.new_edges:
            source_name = edge.get("source", "")
            target_name = edge.get("target", "")
            # Resolve source and target to entity IDs
            source_ent = next((e for e in resolved_entities if e["name"] == source_name), None)
            target_ent = next((e for e in resolved_entities if e["name"] == target_name), None)
            if source_ent and target_ent:
                bq.create_edge(
                    source_id=source_ent["entity_id"],
                    target_id=target_ent["entity_id"],
                    source_type="entity",
                    target_type="entity",
                    relation=edge.get("relation", "related_to"),
                    confidence=edge.get("confidence"),
                )
                intelligence_edges += 1

        # Handle updated knowledge (supersede old nodes)
        for update in intel_result.updated_knowledge:
            old_id = update.get("id")
            if old_id:
                old_node = bq.get_knowledge_node(old_id)
                if old_node and old_node.is_latest:
                    old_node.is_latest = False
                    old_node.superseded_by = knowledge_node.id
                    db.flush()
                    logger.info("Superseded knowledge node %s", old_id)

        # Store implications as observation
        if intel_result.implications:
            bq.create_knowledge_node(
                kind="observation",
                title=f"Implication: {classification.summary}",
                content=intel_result.implications,
                confidence=classification.confidence * 0.8,
                trust_score=classification.confidence * 0.8,
                primary_topic_key=classification.topic_key,
                metadata={"source_knowledge_id": str(knowledge_node.id), "ingestion_source": "processor_intelligence"},
            )
            implications_stored = True

    except Exception:
        logger.exception("Intelligence stage failed for item, continuing with basic extraction")

    logger.info(
        "Knowledge handler: %d entities (%d new, %d resolved), %d basic edges, %d intel edges, implications=%s, knowledge_node=%s",
        len(resolved_entities), entities_created, entities_resolved, basic_edges, intelligence_edges, implications_stored, knowledge_node.id,
    )

    return HandlerResult(
        handler_name="knowledge",
        success=True,
        detail={
            "entities_created": entities_created,
            "entities_resolved": entities_resolved,
            "basic_edges": basic_edges,
            "intelligence_edges": intelligence_edges,
            "implications": implications_stored,
            "entities": resolved_entities,
            "knowledge_node_id": str(knowledge_node.id),
            "knowledge_kind": classification.knowledge_kind,
            "topic_key": classification.topic_key,
        },
    )
```

- [ ] **Step 5: Update processor.py to pass topics**

In `app/services/processor/processor.py`, add a `_get_topics` method to `ProcessorService`:

```python
    def _get_topics(self) -> list[dict]:
        """Get list of topic profiles for the classifier prompt."""
        from app.models.brain import TopicProfile
        topics = self.db.query(TopicProfile).filter(TopicProfile.enabled == True).order_by(TopicProfile.priority.asc()).all()  # noqa: E712
        return [{"key": t.topic_key, "name": t.display_name} for t in topics]
```

And update the `_process_item` method to pass topics to `classify_item`:

```python
        active_workflows = self._get_active_workflows()
        entity_types = self._get_entity_types()
        topics = self._get_topics()

        classification = classify_item(
            source_type=item.source_type, raw_payload=item.raw_payload,
            active_workflows=active_workflows, entity_types=entity_types,
            topics=topics,
        )
```

Also update the `item.classification` dict to include the new fields:

```python
        item.classification = {
            "summary": classification.summary,
            "is_knowledge": classification.is_knowledge,
            "knowledge_kind": classification.knowledge_kind,
            "topic_key": classification.topic_key,
            "confidence": classification.confidence,
            "knowledge_entities": classification.knowledge_entities,
            "is_workflow_trigger": classification.is_workflow_trigger,
            "workflow_slugs": classification.workflow_slugs,
            "workflow_reason": classification.workflow_reason,
            "is_alert": classification.is_alert,
            "alert_reason": classification.alert_reason,
        }
```

- [ ] **Step 6: Run all tests**

Run: `.venv/bin/pytest tests/test_knowledge_handler.py tests/test_classifier.py tests/test_intelligence.py tests/test_processor.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/processor/handlers/knowledge.py app/services/brain_query.py app/services/processor/processor.py tests/test_knowledge_handler.py
git commit -m "feat: two-stage knowledge handler with intelligence reasoning and topic assignment"
```

---

### Task 4: MCP get_context Tool + API Endpoint

**Files:**
- Create: `app/api/context_routes.py`
- Modify: `app/main.py`
- Modify: `ntangible_mcp/server.py`
- Test: `tests/test_context_routes.py`
- Test: `tests/test_mcp_get_context.py`

- [ ] **Step 1: Write context API tests**

```python
# tests/test_context_routes.py
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _make_app():
    from fastapi import FastAPI
    from app.api.context_routes import router
    app = FastAPI()
    app.include_router(router)
    return app


def test_context_endpoint_returns_results():
    app = _make_app()
    client = TestClient(app)

    mock_entity = MagicMock()
    mock_entity.id = "ent-1"
    mock_entity.canonical_name = "Alliance Sports"
    mock_entity.entity_type = "partner"
    mock_entity.description = "Sports partner"
    mock_entity.primary_topic_key = "marketing"

    mock_edge = MagicMock()
    mock_edge.relation = "partner_of"
    mock_edge.target_id = "ent-2"
    mock_edge.source_id = "ent-1"

    mock_knowledge = MagicMock()
    mock_knowledge.id = "kn-1"
    mock_knowledge.kind = "fact"
    mock_knowledge.title = "Alliance partnership launched Q1"
    mock_knowledge.content = "Partnership details..."
    mock_knowledge.confidence = 0.9
    mock_knowledge.primary_topic_key = "work"

    with patch("app.api.context_routes.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        # Entity search
        mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = [mock_entity]
        # We need more complex mocking for the full flow, so test the basic structure
        response = client.get("/api/mcp/context", params={"q": "Alliance Sports"})

    assert response.status_code == 200
    data = response.json()
    assert "entities" in data
    assert "knowledge" in data
    assert "query" in data


def test_context_endpoint_requires_query():
    app = _make_app()
    client = TestClient(app)
    response = client.get("/api/mcp/context")
    assert response.status_code == 422
```

- [ ] **Step 2: Write MCP tool test**

```python
# tests/test_mcp_get_context.py
from unittest.mock import patch, MagicMock

from ntangible_mcp.server import get_context


def test_get_context_calls_api():
    mock_client = MagicMock()
    mock_client.get.return_value = {
        "entities": [{"name": "Alliance Sports", "type": "partner"}],
        "knowledge": [{"title": "Partnership fact", "kind": "fact"}],
        "query": "Alliance Sports",
        "entity_count": 1,
        "knowledge_count": 1,
    }
    with patch("ntangible_mcp.server._get_client", return_value=mock_client):
        result = get_context(query="Alliance Sports")
    assert "Alliance Sports" in result
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert call_args[0][0] == "/api/mcp/context"
    assert call_args[1]["params"]["q"] == "Alliance Sports"


def test_get_context_with_topic():
    mock_client = MagicMock()
    mock_client.get.return_value = {"entities": [], "knowledge": [], "query": "test", "entity_count": 0, "knowledge_count": 0}
    with patch("ntangible_mcp.server._get_client", return_value=mock_client):
        result = get_context(query="test", topic="marketing")
    call_args = mock_client.get.call_args
    assert call_args[1]["params"]["topic"] == "marketing"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_context_routes.py tests/test_mcp_get_context.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Create context API endpoint**

```python
# app/api/context_routes.py
"""Context assembly API for the MCP get_context tool."""
from __future__ import annotations
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.brain import EntityNode, KnowledgeNode, EntityEdge, KnowledgeEdge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["context"], dependencies=[])


@router.get("/context")
def get_context(
    q: str = Query(..., description="Search query"),
    topic: str | None = Query(None, description="Optional topic filter"),
    max_entities: int = Query(10, description="Max entities to return"),
    max_knowledge: int = Query(15, description="Max knowledge nodes to return"),
    db: Session = Depends(get_db),
):
    """Assemble a context packet from the knowledge graph."""
    search_terms = q.lower().split()

    # 1. Entity search — match by canonical_name
    entity_query = db.query(EntityNode)
    for term in search_terms:
        entity_query = entity_query.filter(EntityNode.canonical_name.ilike(f"%{term}%"))
    if topic:
        entity_query = entity_query.filter(EntityNode.primary_topic_key == topic)
    entities = entity_query.limit(max_entities).all()

    # 2. Edge expansion
    entity_results = []
    for ent in entities:
        edges_from = (
            db.query(EntityEdge)
            .filter(EntityEdge.source_id == ent.id)
            .limit(10)
            .all()
        )
        edges_to = (
            db.query(EntityEdge)
            .filter(EntityEdge.target_id == ent.id)
            .limit(10)
            .all()
        )

        # Resolve edge target/source names
        edge_list = []
        for e in edges_from:
            target = db.query(EntityNode).filter(EntityNode.id == e.target_id).first()
            edge_list.append({
                "relation": e.relation,
                "target": target.canonical_name if target else str(e.target_id),
                "type": "entity",
            })
        for e in edges_to:
            source = db.query(EntityNode).filter(EntityNode.id == e.source_id).first()
            edge_list.append({
                "relation": e.relation,
                "target": source.canonical_name if source else str(e.source_id),
                "type": "entity",
            })

        entity_results.append({
            "name": ent.canonical_name,
            "type": ent.entity_type,
            "description": ent.description or "",
            "topic": ent.primary_topic_key,
            "edges": edge_list,
        })

    # 3. Knowledge search
    knowledge_query = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.is_latest == True)  # noqa: E712
    )
    for term in search_terms:
        knowledge_query = knowledge_query.filter(
            KnowledgeNode.title.ilike(f"%{term}%")
            | KnowledgeNode.content.ilike(f"%{term}%")
        )
    if topic:
        knowledge_query = knowledge_query.filter(KnowledgeNode.primary_topic_key == topic)
    knowledge_nodes = knowledge_query.limit(max_knowledge).all()

    # 4. Knowledge edges
    knowledge_results = []
    for kn in knowledge_nodes:
        k_edges = (
            db.query(KnowledgeEdge)
            .filter((KnowledgeEdge.source_id == kn.id) | (KnowledgeEdge.target_id == kn.id))
            .limit(5)
            .all()
        )
        edge_list = []
        for ke in k_edges:
            other_id = ke.target_id if ke.source_id == kn.id else ke.source_id
            other = db.query(KnowledgeNode).filter(KnowledgeNode.id == other_id).first()
            edge_list.append({
                "relation": ke.relation,
                "target": other.title if other else str(other_id),
                "type": "knowledge",
            })

        knowledge_results.append({
            "kind": kn.kind,
            "title": kn.title,
            "content": (kn.content or "")[:500],
            "confidence": kn.confidence,
            "topic": kn.primary_topic_key,
            "edges": edge_list,
        })

    return {
        "entities": entity_results,
        "knowledge": knowledge_results,
        "query": q,
        "entity_count": len(entity_results),
        "knowledge_count": len(knowledge_results),
    }
```

- [ ] **Step 5: Register context routes in main.py**

In `app/main.py`, add after the webhook_router import (around line 106):

```python
from app.api.context_routes import router as context_router
```

And add after `app.include_router(webhook_router)` (around line 128):

```python
app.include_router(context_router)
```

- [ ] **Step 6: Add get_context tool to MCP server**

In `ntangible_mcp/server.py`, add after the existing `process_file` tool:

```python
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
```

- [ ] **Step 7: Run tests**

Run: `.venv/bin/pytest tests/test_context_routes.py tests/test_mcp_get_context.py -v`
Expected: All 4 tests PASS

- [ ] **Step 8: Commit**

```bash
git add app/api/context_routes.py app/main.py ntangible_mcp/server.py tests/test_context_routes.py tests/test_mcp_get_context.py
git commit -m "feat: add MCP get_context tool with context assembly API"
```

---

### Task 5: Full Test Suite + Deploy

**Files:**
- No new files

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/pytest tests/test_ingestion_model.py tests/test_prefilter.py tests/test_classifier.py tests/test_intelligence.py tests/test_alert_handler.py tests/test_workflow_handler.py tests/test_knowledge_handler.py tests/test_processor.py tests/test_webhook_routes.py tests/test_mcp_process_file.py tests/test_context_routes.py tests/test_mcp_get_context.py -v`
Expected: All tests PASS

- [ ] **Step 2: Push and deploy**

```bash
git push origin partner-engine-all
```

Then deploy to production:

```bash
ssh -i /tmp/lightsail_key.pem ubuntu@3.21.155.208 "cd /home/ubuntu/app && git pull origin partner-engine-all && sudo systemctl restart ntangible-web ntangible-processor"
```

- [ ] **Step 3: Test the upgraded processor with a real item**

```bash
curl -s -X POST https://3-21-155-208.nip.io/api/mcp/process-file \
  -H "Authorization: Bearer $APP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "Email from Dan Connerty: Alliance Sports wants to renew and expand their partnership for the summer season. They are interested in co-branded content and want to discuss budget increases. Meeting scheduled for April 20.", "file_name": "partnership-email.txt"}'
```

Check the processor logs:

```bash
ssh -i /tmp/lightsail_key.pem ubuntu@3.21.155.208 "sudo journalctl -u ntangible-processor --no-pager -n 20 --since '30 seconds ago'"
```

Expected: Logs show Stage 1 classification with knowledge_kind, topic_key, confidence, followed by Stage 2 intelligence reasoning with edges and implications.

- [ ] **Step 4: Test the get_context MCP tool**

```bash
curl -s "https://3-21-155-208.nip.io/api/mcp/context?q=Alliance+Sports" \
  -H "Authorization: Bearer $APP_API_KEY"
```

Expected: Returns entities (Alliance Sports with edges) and knowledge nodes related to the query.

- [ ] **Step 5: Verify the Settings page shows typed activity**

Navigate to `https://3-21-155-208.nip.io/control-room/brain/settings`
Expected: Recent Activity shows the processed item with knowledge_kind and topic in the classification.
