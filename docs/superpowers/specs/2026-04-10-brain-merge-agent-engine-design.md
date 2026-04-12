# Brain Merge: Agent-Engine into NTangible Marketing

**Date:** 2026-04-10
**Status:** Approved
**Approach:** B — Import into existing schema, minimal schema changes

## Goal

Combine the agent-engine brain (488 entities, 576 knowledge nodes, 335 knowledge edges, 282 entity edges) into the ntangible_marketing database so the marketing app has access to the full NTangible knowledge graph. The existing marketing data (workflows, channels, pillars, drafts, content brain items) must continue working unchanged.

## Architecture

The combined brain follows a hierarchy:

```
NTangible (entity: company)
  ├── People (person): Dan Connerty, Elliot Sones, Shalin Patel, ...
  ├── Companies: BRKTHRU, Cerebro Sports, Vercel, ...
  ├── Orgs: 1871, NCAA, Chicago Cubs, ...
  ├── Products: Clutch Factor, NGauge, NTerpret, ...
  ├── Partners (entity_type=partner): Alliance Fastpitch, Future Stars Series, High Level Throwing, RFK Racing
  ├── Clients (entity_type=client): Boston College, Michigan State University, Hofstra University
  ├── Competitors (entity_type=competitor): S2 Cognition, Scorability
  │
  └── [has_topic] "marketing" (topic_profile)
        ├── Workflows (workflow): Tuesday Thought Leadership, FSS Leaderboard, ...
        │   ├── [publishes_to] Channels: LinkedIn, Instagram, X, Newsletter
        │   ├── [uses_pillar] Pillars: Thought Leadership, Client Proof, ...
        │   └── [produced] Knowledge nodes (drafts)
        ├── Knowledge (knowledge_nodes, primary_topic_key='marketing')
        │   ├── Drafts, Approved Claims, Reference Content, Schedule Rules, Observations
        └── Content Brain Items (content_brain_item — unchanged)
            ├── LinkedIn (129), Instagram (25), YouTube (21), Web (52)
```

**Topic key rules (single source of truth):**
- Marketing entities keep `primary_topic_key = 'marketing'`.
- Agent-engine knowledge nodes keep their original `primary_topic_key` (work, people, projects, finance).
- Agent-engine entity nodes: entities that have a `primary_topic_key` in agent-engine's `entity_topic_links` table keep that value. Entities with no topic link get `primary_topic_key = NULL`.
- **Topic views only show explicitly tagged nodes.** `get_graph_data(topic_key="work")` returns only entities and knowledge where `primary_topic_key = "work"`, plus edges between those nodes. NULL-topic entities are visible only in the `topic=all` view. This keeps topic views predictable — the graph pipeline renders only nodes in the `entities`/`knowledge` lists returned by `get_graph_data` (brain_query.py:378, routes.py:4069, graph.html:79), so returning an edge without its adjacent node would produce dangling references.

## Schema Mapping

No schema migration needed. Agent-engine data maps into existing ntangible_marketing columns:

### entity_nodes

| agent-engine | ntangible_marketing | notes |
|---|---|---|
| `id` | `id` | preserve original UUIDs |
| `tenant_id` | (drop) | single-tenant app |
| `entity_type` | `entity_type` | direct map |
| `canonical_name` | `canonical_name` | direct map |
| (none) | `slug` | generate from canonical_name |
| `description` | `description` | direct map |
| `status` | `status` | direct map |
| (none) | `primary_topic_key` | from entity_topic_links if present, else NULL; 'marketing' for existing marketing entities |
| `metadata` | `metadata` | carry over, add `"source": "agent_engine"` |

### entity_edges

| agent-engine | ntangible_marketing | notes |
|---|---|---|
| `from_entity_id` | `source_id` | rename |
| `to_entity_id` | `target_id` | rename |
| (none) | `source_type` | `'entity'` |
| (none) | `target_type` | `'entity'` |
| `relation` | `relation` | direct map |
| `confidence` | `confidence` | direct map |
| `valid_from`, `valid_until`, `status` | `metadata` | stash in jsonb |

### knowledge_nodes

| agent-engine | ntangible_marketing | notes |
|---|---|---|
| `id` | `id` | preserve |
| `tenant_id` | (drop) | |
| `kind` | `kind` | direct map |
| `title` | `title` | direct map |
| `content` | `content` | direct map |
| `primary_topic_key` | `primary_topic_key` | direct map |
| `confidence` | `confidence` | direct map |
| `trust_score` | `trust_score` | direct map |
| `is_core`, `recency_score`, `extraction_run_id` | `metadata` | stash in jsonb |
| `version`, `superseded_by`, `is_latest` | same columns | direct map |
| `status` | `status` | direct map |

### knowledge_edges

| agent-engine | ntangible_marketing | notes |
|---|---|---|
| `from_knowledge_id` | `source_id` | rename |
| `to_knowledge_id` | `target_id` | rename |
| `relation` | `relation` | direct map |
| `confidence` | `confidence` | direct map |

## Entity Dedup Plan

### Overlapping entities (marketing node wins, agent-engine data merges in)

Marketing entities that exist in agent-engine get their marketing node ID and entity_type preserved. The marketing entity_type (partner/client/competitor) stays as-is because app services query by these types. A relationship edge is also created to express the role in the graph.

| marketing entity | agent-engine match(es) | new edge |
|---|---|---|
| Alliance Fastpitch (partner) | Alliance Fastpitch (org), The Alliance Fastpitch LLC (company), Alliance (org) | `partner_of → NTangible` |
| Future Stars Series (partner) | Future Stars Series (company), FSS (org) | `partner_of → NTangible` |
| High Level Throwing (partner) | High Level Throwing (org) | `partner_of → NTangible` |
| RFK Racing (partner) | RFK Racing (org) | `partner_of → NTangible` |
| Boston College (client) | Boston College (org) | `client_of → NTangible` |
| Michigan State (client) | Michigan State University (org) | `client_of → NTangible` |
| Hofstra (client) | Hofstra University (org) | `client_of → NTangible` |
| S2 Cognition (competitor) | S2 Cognition (company) — note: also exists in marketing as separate competitor node | `competes_with → NTangible` |
| Scorability (competitor) | Scorability (company) — note: also exists in marketing as separate competitor node | `competes_with → NTangible` |

### Person entity dedup (agent-engine internal)

Only import people with >= 1 edge (25 real people). Merge duplicates:

| canonical (keep) | duplicates (skip) |
|---|---|
| Pranay Ramash | Pranay R, Pranay R., Pranay R22, Patel Shalin |
| Isaac Sullivan | Isaac |
| Howard Schwartz | Howie Schwartz |
| Elliot Sones | Elliot (Form Submitter), elliotsenos16@gmail.com |

### Company/org dedup (agent-engine internal)

| canonical (keep) | duplicates (skip) |
|---|---|
| NTangible | NTangible Inc. |
| Alliance Fastpitch | The Alliance Fastpitch LLC, Alliance |
| HRMC | HRMC Inc. |
| Honsberger Physiotherapy & Biomechanics | Honsberger Physio+ |
| 1871 | 1871 Innovation Lab |
| MaRS | MaRS Accelerator |

### Person entities filtered out (no edges, noise)

All ~327 person entities with 0 edges are skipped. These are code variables, UI labels, and phrases misclassified as people by the extraction pipeline.

## Import Script Steps

One-time Python migration script. Runs in a single transaction for rollback safety.

### Step 1: Build dedup map

Query both databases. Build a dictionary mapping agent-engine IDs to ntangible_marketing IDs for overlapping entities. Build a second dictionary mapping duplicate agent-engine IDs to their canonical agent-engine ID.

### Step 2: Filter person entities

Query agent-engine entity_edges to find people with >= 1 edge. Only those pass the filter.

### Step 3: Import non-overlapping entities

Insert all agent-engine entities that passed filtering and don't already exist in marketing. Generate slugs. Set `metadata.source = 'agent_engine'`.

### Step 4: Merge overlapping entities (preserve entity_type)

For overlapping entities (partner/client/competitor):
1. **Keep the existing marketing entity node and its entity_type unchanged.** The competitor dashboard (`competitor_service.py:22`) queries `entity_type="competitor"`, and the competitor ingestion path (`competitor_service.py:169`) creates new competitors with that type. Changing it would break these flows. Same applies to partner/client types used elsewhere.
2. Merge agent-engine descriptions and metadata into the existing marketing node (additive only, don't overwrite existing fields). Add `metadata.agent_engine_id` pointing to the original agent-engine UUID, and `metadata.agent_engine_type` recording the agent-engine type (org/company).
3. Repoint any existing marketing edges that referenced duplicate agent-engine nodes (e.g. FSS, Alliance) to the canonical marketing node.
4. Create new relationship edges: `partner_of`, `client_of`, `competes_with` → NTangible entity (in addition to keeping the entity_type).

### Step 5: Import knowledge nodes

All active + is_latest knowledge nodes from agent-engine (410 nodes). Stash `is_core`, `recency_score`, `extraction_run_id` in metadata. Remap `superseded_by` through dedup map.

### Step 6: Import edges

All entity_edges from agent-engine, remapping `from_entity_id`/`to_entity_id` through the dedup map into `source_id`/`target_id`. Set `source_type='entity'`, `target_type='entity'`. Skip edges where either endpoint was filtered out.

All knowledge_edges from agent-engine, remapping `from_knowledge_id`/`to_knowledge_id` through dedup map.

### Step 7: Rewrite metadata entity ID references

Several services store entity IDs inside JSON metadata and use them as runtime foreign keys:
- `scheduler.py:86` reads `workflow_entity_id` from schedule_rule metadata
- `workflow_engine.py:195` reads `workflow_entity_id` from trigger node metadata
- `competitor_service.py:37` reads `competitor_entity_id` from signal metadata
- `competitor_service.py:192` reads `source_entity_id` from observation metadata

The migration script must scan all knowledge_nodes and entity_nodes metadata for UUID values that appear in the dedup map, and rewrite them to point to the canonical node ID. Specifically:
1. Query all knowledge_nodes where `metadata` contains any key ending in `_entity_id` or `_id`.
2. For each match, check if the UUID value appears in the dedup remap dictionary.
3. If so, update it to the canonical ID.
4. Same scan for entity_nodes metadata.

This ensures the scheduler, workflow engine, and competitor service continue resolving their metadata-embedded references correctly.

### Step 8: Add topic profiles and assign topic keys

1. Insert topic profiles for each agent-engine topic (work, people, projects, finance) alongside the existing marketing topic.
2. Ensure all marketing-origin entity nodes have `primary_topic_key='marketing'`.
3. For agent-engine entities: query `entity_topic_links` in the agent-engine DB to find topic assignments. Set `primary_topic_key` accordingly. Entities with no topic link get `primary_topic_key = NULL`.
4. Agent-engine knowledge nodes keep their `primary_topic_key` as-is from the source DB (work, people, projects, finance).

## What Stays Unchanged

- `content_brain_item` table (228 rows) — untouched
- `content_brain_metric_snapshot` (163 rows) — untouched
- `content_brain_asset` (304 rows) — untouched
- `content_source_target` / `content_source_snapshot` — untouched
- `sports_calendar_windows` (14 rows) — untouched
- `lead_accounts` / `lead_contacts` — untouched
- `competitor_observations` / `competitor_sources` — untouched (these use their own IDs, separate from entity_nodes)
- All marketing workflows, content pillars, publishing channels — untouched (these are marketing-only entities)
- All marketing knowledge nodes (drafts, claims, reference content, etc.) — untouched
- All marketing entity/knowledge edges — repointed where dedup applies, otherwise untouched

## App Code Changes (required for imported data to be usable)

### 1. MemoryRetrievalService — add factual context retrieval channel

The current retrieval pipeline has two problems for imported data:

1. `_load_candidate_items` (memory_retrieval.py:308) only loads `observation` and `reference_content` nodes.
2. Even if we add `fact` to that pool, `search()` (memory_retrieval.py:255-257) filters by bucket status (`approved`/`rejected`) and platform. Imported facts are `active` status and have no platform — they'd still be dropped.
3. `build_generation_context` (memory_retrieval.py:277) only returns `approved_examples` and `rejected_examples` buckets, and the prompt assembler (prompt_assembler.py:72-73) only consumes those two.

**Fix:** Add a third retrieval channel — `brain_facts` — that is not bucketed by status/platform. This gives the prompt assembler access to company intelligence, partnership details, and product information from the imported brain.

**memory_retrieval.py changes:**
```python
def build_generation_context(self, *, query, platform, workflow_slug=None,
                             approved_limit=5, rejected_limit=2, facts_limit=5):
    approved = self.search(query=query, platform=platform,
                           bucket=_BucketCompat("approved"),
                           workflow_slug=workflow_slug, limit=approved_limit)
    rejected = self.search(query=query, platform=platform,
                           bucket=_BucketCompat("rejected"),
                           workflow_slug=workflow_slug, limit=rejected_limit)
    brain_facts = self._search_brain_facts(query=query, limit=facts_limit)
    memory_ids = [item["id"] for item in approved + rejected + brain_facts]
    return {
        "approved_examples": approved,
        "rejected_examples": rejected,
        "brain_facts": brain_facts,
        "memory_ids": memory_ids,
    }

def _search_brain_facts(self, *, query: str, limit: int = 5) -> list[dict]:
    """Search fact nodes by keyword relevance. No bucket/platform filtering."""
    query_tokens = self._tokenize(query)
    facts = self.bq.list_knowledge_by_kind("fact", limit=250)
    scored = []
    for item in facts:
        score = self._score_item(item, query_tokens, None, None, None)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda v: (v[0], v[1].created_at), reverse=True)
    return [self._serialize_item(item, score) for score, item in scored[:limit]]
```

**prompt_assembler.py changes:**
```python
retrieval = memory.build_generation_context(
    query=retrieval_query,
    platform=workflow.platform,
    workflow_slug=workflow.slug,
    approved_limit=config.retrieval.max_examples,
    rejected_limit=min(2, config.retrieval.max_examples),
    facts_limit=5,
)
approved_text = self._examples_block("Approved examples", retrieval["approved_examples"])
rejected_text = self._examples_block("Avoid repeating these rejected patterns", retrieval["rejected_examples"])
facts_text = self._facts_block(retrieval["brain_facts"])  # new helper

# Include facts_text in the system prompt assembly
```

The `_facts_block` helper formats brain facts as a "Company context" section in the system prompt — not as examples to imitate, but as factual grounding the LLM can draw on.

### 2. BrainQuery.get_graph_data — support topic=None for full brain view

`brain_query.py:362` filters entities and knowledge strictly by `primary_topic_key == topic_key`. Imported agent-engine entities have `primary_topic_key = NULL`, so they're invisible in the graph.

**Fix:** Add an optional `topic_key=None` mode that returns all nodes (the "full brain" view). Keep the default as `"marketing"` so existing views are unaffected.

```python
def get_graph_data(self, *, topic_key: str | None = "marketing") -> dict:
    if topic_key is None:
        entities = self.db.query(EntityNode).all()
        knowledge = self.db.query(KnowledgeNode).filter(KnowledgeNode.is_latest == True).all()
    else:
        entities = self.db.query(EntityNode).filter(EntityNode.primary_topic_key == topic_key).all()
        knowledge = self.db.query(KnowledgeNode).filter(KnowledgeNode.primary_topic_key == topic_key).all()
    # ... rest unchanged
```

### 3. Graph routes — add topic query parameter

`routes.py:4005` (`/graph`) and `routes.py:4068` (`/brain/graph`) are hardcoded to `topic_key="marketing"`.

**Fix:** Accept an optional `?topic=` query parameter. Default to `"marketing"`. Pass `topic=all` to see the full brain.

```python
@web_router.get("/brain/graph")
def brain_graph_view(request: Request, topic: str = "marketing", db: Session = Depends(get_db)):
    effective_topic = None if topic == "all" else topic
    data = BrainQuery(db).get_graph_data(topic_key=effective_topic)
    # ... rest unchanged
```

### 4. Graph template — add topic switcher

Add a simple dropdown/button bar to `graph.html` that lets the user switch between topics: Marketing (default), Work, People, Projects, Finance, All. Each option reloads the page with `?topic=<key>`.

## What Stays Unchanged

- `content_brain_item` table (228 rows) — untouched
- `content_brain_metric_snapshot` (163 rows) — untouched
- `content_brain_asset` (304 rows) — untouched
- `content_source_target` / `content_source_snapshot` — untouched
- `sports_calendar_windows` (14 rows) — untouched
- `lead_accounts` / `lead_contacts` — untouched
- `competitor_observations` / `competitor_sources` — untouched (these use their own IDs, separate from entity_nodes)
- All marketing workflows, content pillars, publishing channels — untouched (these are marketing-only entities)
- All marketing knowledge nodes (drafts, claims, reference content, etc.) — untouched
- All marketing entity/knowledge edges — repointed where dedup applies, otherwise untouched
- Scheduler, workflow engine, competitor service runtime behavior — preserved by metadata ID rewrite (Step 7) and entity_type preservation (Step 4)
