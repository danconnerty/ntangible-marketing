# Layer-Aware Processor Design Spec

**Date:** 2026-04-11
**Status:** Draft
**Scope:** Redesign the processing pipeline to flow through Source → Knowledge → Intelligence layers, plus a new MCP `get_context` tool for runtime context assembly.

## Overview

Upgrade the existing processor from a flat "extract entities and edges" pipeline to a layer-aware system that:
- Classifies knowledge by kind (fact, event, task, deadline, observation)
- Assigns topics from the brain's topic taxonomy
- Scores confidence on extracted knowledge
- Reasons about how new knowledge connects to, supports, contradicts, or updates existing knowledge in the graph
- Provides an MCP tool for on-demand context assembly from the graph

## Goals

- Every piece of ingested knowledge gets a proper kind, topic, and confidence score
- New knowledge is immediately connected to the existing graph through reasoned intelligence edges
- The LLM can reason about implications and contradictions using existing graph context
- Claude can pull structured brain context for any task via the `get_context` MCP tool
- Cost stays under $10/month at expected volume (~100 items/day)

## Non-Goals

- Full source layer with segments and embeddings (lightweight provenance via ingestion_queue is sufficient)
- Pre-compiled intelligence packets (on-demand via MCP tool instead)
- Changes to existing content generation agents' context assembly (MemoryRetrievalService stays as-is)
- Context layer changes — that's the MCP tool's job, not the processor's

---

## Architecture

### Processing Pipeline

```
INTAKE → PRE-FILTER (rules) → STAGE 1 (classify + extract) → STAGE 2 (intelligence) → GRAPH WRITE
```

The pre-filter and intake sources remain unchanged from the current processor. The changes are in what happens after pre-filtering.

### Stage 1: Classify + Extract (LLM Call #1)

Single LLM call to gpt-5.4-nano with structured JSON output. Same cheap model as today.

**Input context:**
- Raw content (email body, calendar event, file text)
- Source type (gmail, calendar, mcp_file, manual_upload)
- Available topics: list of topic_key + display_name from `topic_profiles`
- Available entity types: the 12 entity types in the brain (person, company, org, partner, client, competitor, product, topic, content_pillar, workflow, publishing_channel, place)
- Active workflows with names and descriptions

**Output schema:**

```json
{
  "summary": "One-line summary",
  "knowledge_kind": "fact|event|task|deadline|observation",
  "topic_key": "marketing|work|people|projects|finance",
  "confidence": 0.85,
  "is_knowledge": true,
  "entities": [
    {"name": "Alliance Sports", "type": "partner", "relation": "contract_expansion"}
  ],
  "is_workflow_trigger": true,
  "workflow_slugs": ["partner-update"],
  "workflow_reason": "Partner contract change",
  "is_alert": false,
  "alert_reason": null
}
```

**New fields vs current classifier:**
- `knowledge_kind` — from the brain's knowledge taxonomy (fact, event, task, deadline, observation)
- `topic_key` — assigned from available topics
- `confidence` — 0.0 to 1.0 rating of extraction confidence
- Entity `type` — uses the full 12-type taxonomy instead of free-form

### Stage 2: Intelligence (LLM Call #2)

Only runs when Stage 1 marks the item as knowledge (`is_knowledge` is true and `knowledge_kind` is set). Uses the same cheap model.

**Input context:**
- Stage 1 output (summary, entities, knowledge kind, confidence)
- For each entity resolved from the graph: their existing entity edges (up to 10) and related knowledge nodes (up to 10)
- The new knowledge node that was just created

**Output schema:**

```json
{
  "new_edges": [
    {
      "source": "entity_or_knowledge_name",
      "target": "entity_or_knowledge_name",
      "relation": "supports|contradicts|depends_on|causes|updates|related_to",
      "confidence": 0.9,
      "edge_type": "entity|knowledge"
    }
  ],
  "updated_knowledge": [
    {
      "id": "existing_knowledge_node_id",
      "update": "Description of what changed — this fact is now superseded"
    }
  ],
  "contradictions": [
    {
      "existing_id": "knowledge_node_id",
      "description": "New information contradicts previous understanding that..."
    }
  ],
  "implications": "Free-text reasoning about what this means in context"
}
```

**What Stage 2 produces:**
- **New entity edges** — typed relationships between entities (works_at, partner_of, attended, etc.)
- **New knowledge edges** — logical connections between knowledge nodes (supports, contradicts, depends_on, updates)
- **Updated knowledge** — flags existing knowledge nodes that should be marked as superseded or updated
- **Contradictions** — explicitly flags when new information conflicts with existing knowledge
- **Implications** — stored as a new observation knowledge node connected to the source knowledge

### Graph Write

After both stages complete, the knowledge handler writes to the graph:

1. **Upsert entities** — resolve by slug, create if new. Assign `primary_topic_key` based on entity type and Stage 1's topic assignment.
2. **Create knowledge node** — typed by `knowledge_kind`, with `primary_topic_key`, `confidence`, and `trust_score` set. Reference the `ingestion_queue` item ID in metadata for provenance.
3. **Create entity edges** — from Stage 1 (between co-occurring entities) and Stage 2 (reasoned relationships with confidence scores).
4. **Create knowledge edges** — from Stage 2 (supports, contradicts, updates between knowledge nodes).
5. **Update existing knowledge** — if Stage 2 flagged superseded facts, set `is_latest = false` and `superseded_by` pointing to the new node.
6. **Store implications** — if Stage 2 produced implications text, create an observation knowledge node.

### Entity Topic Assignment

When creating new entities, `primary_topic_key` is assigned based on:
- If the Stage 1 classifier assigned a topic, use it
- Fallback by entity type: person → people, company/org/place → work, product → projects, partner/client/competitor/workflow/content_pillar/publishing_channel → marketing, topic → use classifier's topic_key

---

## MCP `get_context` Tool

New tool added to `ntangible_mcp/server.py`. Independent of the processing pipeline — queries the graph at runtime.

### Tool Definition

```
get_context(
  query: str,              # What context is needed (e.g., "Alliance Sports partnership")
  topic: str | None,       # Optional topic filter
  max_entities: int = 10,  # Max entities to return
  max_knowledge: int = 15  # Max knowledge nodes to return
)
```

### API Endpoint

New endpoint: `GET /api/mcp/context`

Query parameters: `q` (required), `topic` (optional), `max_entities` (optional), `max_knowledge` (optional)

### Context Assembly Logic

1. **Entity search** — search entities by canonical_name matching (case-insensitive contains) and slug matching against the query terms
2. **Edge expansion** — for each matched entity, fetch their entity edges (up to 10 per entity)
3. **Knowledge search** — search knowledge nodes by full-text search (tsvector) against the query, filtered by topic if provided
4. **Knowledge edges** — for matched knowledge nodes, fetch their knowledge edges
5. **Assembly** — return a structured packet with entities (name, type, description, edges), knowledge (kind, title, content, confidence, topic), and a summary line

### Response Format

```json
{
  "entities": [
    {
      "name": "Alliance Sports",
      "type": "partner",
      "description": "Sports technology partner",
      "topic": "marketing",
      "edges": [
        {"relation": "partner_of", "target": "NTangible", "type": "entity"},
        {"relation": "contract_expansion", "target": "NTangible", "type": "entity"}
      ]
    }
  ],
  "knowledge": [
    {
      "kind": "fact",
      "title": "Alliance Sports doubling contract for next season",
      "content": "Email from Dan confirmed expansion...",
      "confidence": 0.85,
      "topic": "work",
      "edges": [
        {"relation": "updates", "target": "Initial partnership terms", "type": "knowledge"}
      ]
    }
  ],
  "query": "Alliance Sports partnership",
  "entity_count": 2,
  "knowledge_count": 3
}
```

---

## Changes to Existing Code

### Modified Files

**`app/services/processor/classifier.py`**
- Update `ClassificationResult` dataclass: add `knowledge_kind`, `topic_key`, `confidence` fields
- Update `build_classifier_prompt`: include topic list and full entity type taxonomy in the system prompt
- Update output schema to include new fields
- Add `parse_classification` handling for new fields

**`app/services/processor/handlers/knowledge.py`**
- After entity resolution, fetch existing graph context for resolved entities (edges + related knowledge)
- Make Stage 2 LLM call with graph context
- Create typed knowledge nodes with `kind`, `primary_topic_key`, `confidence`
- Create entity edges from Stage 2 output
- Create knowledge edges from Stage 2 output
- Handle `updated_knowledge` — supersede existing nodes
- Store implications as observation knowledge nodes
- Assign `primary_topic_key` on new entities based on type + classifier output

**`app/services/processor/processor.py`**
- Pass topic list to classifier (query `topic_profiles`)
- No structural changes — the two-stage logic lives in the knowledge handler

**`app/main.py`**
- Register `context_routes` router

### New Files

**`app/services/processor/intelligence.py`**
- `build_intelligence_prompt(stage1_output, graph_context)` — builds the Stage 2 prompt
- `parse_intelligence_output(raw)` — parses Stage 2 JSON output into a typed result
- `IntelligenceResult` dataclass

**`app/api/context_routes.py`**
- `GET /api/mcp/context` endpoint
- Context assembly logic: entity search, edge expansion, knowledge search

**`ntangible_mcp/server.py`** (modified)
- Add `get_context` tool that calls `/api/mcp/context`

**`ntangible_mcp/client.py`** (modified)
- Add `get` method with query params support if not already present

### New Tests

- `tests/test_intelligence.py` — Stage 2 prompt building, output parsing
- `tests/test_context_routes.py` — context API endpoint
- `tests/test_mcp_get_context.py` — MCP tool

---

## File Structure

```
app/services/processor/
├── __init__.py                 # unchanged
├── prefilter.py                # unchanged
├── classifier.py               # modified: richer output schema
├── intelligence.py             # NEW: Stage 2 intelligence reasoning
├── processor.py                # modified: pass topics to classifier
└── handlers/
    ├── __init__.py             # unchanged
    ├── base.py                 # unchanged
    ├── knowledge.py            # modified: two-stage processing, typed knowledge
    ├── workflow.py             # unchanged
    └── alert.py                # unchanged

app/api/
├── context_routes.py           # NEW: GET /api/mcp/context

ntangible_mcp/
├── server.py                   # modified: add get_context tool
├── client.py                   # modified: add query param support to get
```

---

## Cost Estimate

| Component | Per Item | Monthly (100 items/day) |
|-----------|---------|------------------------|
| Stage 1 classifier | ~$0.001 | ~$3 |
| Stage 2 intelligence (~70% of items) | ~$0.002 | ~$4.20 |
| **Total** | | **~$7.20/month** |

Stage 2 only fires for knowledge items — filtered noise and non-knowledge items skip it entirely.
