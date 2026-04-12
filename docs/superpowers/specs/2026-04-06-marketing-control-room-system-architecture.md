# NTangible Marketing Control Room — Canonical System Architecture

> **Purpose:** This is the single source-of-truth architecture document for the NTangible marketing control room. Any future agent should read this file first, then the detailed implementation plan, before changing code.
>
> **Primary companion docs:**
> - [manual-first-marketing-control-room-design.md](/Users/elliot18/Desktop/Home/Projects/ntangible_marketing/docs/superpowers/specs/2026-04-06-manual-first-marketing-control-room-design.md)
> - [manual-first-marketing-control-room.md](/Users/elliot18/Desktop/Home/Projects/ntangible_marketing/docs/superpowers/plans/2026-04-06-manual-first-marketing-control-room.md)
>
> **Audience:** engineering agents, implementation agents, code reviewers, and operators who need to understand how the full workflow is supposed to fit together.

---

## 1. Product Outcome

NTangible needs one internal app that acts as a **marketing control room**.

The operator should be able to:

1. open one app
2. see what content exists for today
3. know why each draft was generated
4. review content manually by default
5. post, schedule, reject, or pause content
6. move trusted workflows from manual to automatic later
7. inspect rejected and expired history
8. search past approved/rejected content in the brain
9. ask Claude to improve the workflow that creates future drafts

The app is not just “Claude with memory.” It is an operational system with:

- triggers
- workflows
- workflow versions
- queues
- review actions
- publication records
- content history
- analytics
- a UI for operating all of it

---

## 2. What Exists Today Vs. The Final Target

### What Exists In The Repo Today

The repo already has partial implementation of early phases:

- an **X/Twitter generation + compliance + publish backend**
- a **LinkedIn generation + compliance + publish backend**
- a **public-content brain** for ingesting public web/social sources
- FastAPI routes and SQLAlchemy models for the above
- tests for those backend slices

These are useful building blocks, but they are not yet one coherent operator product.

### What The Final System Must Become

The final system must be a **unified control room** with:

- one queue model for all platforms
- one workflow model for all content types
- visible trigger provenance
- manual/automatic handling modes
- rejected and expired history
- a workflow-aware content brain
- a Claude-driven workflow improvement loop
- one operator UI

### Important Rule

Current X, LinkedIn, and content-brain implementations should be treated as **partial subsystems**, not as the final architecture.

Agents must reuse them where possible, but must not force the control-room design to fit old table shapes if those shapes block the intended workflow.

---

## 3. Core Product Decisions

These decisions are locked in and override earlier automation-first assumptions from the original blueprint.

### 3.1 Manual-First Rollout

Every new workflow starts in `manual` mode.

That means:

- the system generates a draft
- the draft appears in the `Manual` tab
- a human decides what to do

### 3.2 Automatic Is Earned, Not Default

A workflow only becomes `automatic` after the team is comfortable with it.

That means:

- the same trigger and workflow still exist
- the mode changes from `manual` to `automatic`
- future drafts publish at a specific configured time

### 3.3 Trigger Provenance Must Always Be Visible

Every draft must show **why it exists**.

Allowed trigger origins:

- `calendar`
- `external`
- `manual_request`

### 3.4 Manual Items Are All-Day Items

Manual items:

- appear in the manual queue
- appear in the calendar’s all-day lane
- may show a recommended best time
- do not auto-post

### 3.5 Automatic Items Have Exact Publish Times

Automatic items:

- appear in the automatic tab
- appear in timed calendar slots
- publish at the configured time

### 3.6 End-Of-Day Expiry For Manual Items

If a manual item is not acted on by the end of the day in the workflow/account timezone:

- it leaves the active queue
- it moves to `Expired`
- it becomes read-only history

### 3.7 Rejected And Expired Mean Different Things

`Rejected` means:

- the draft was reviewed
- the draft was bad or wrong
- the operator rejected it

`Expired` means:

- the draft was not acted on in time
- it may or may not have been good

These must stay separate because Claude should learn differently from them.

### 3.8 Claude Improves Workflows, Not One-Off Posts

Operators do not primarily “rewrite this post.”
They say “fix the process that made this post.”

That means:

- rejected/low-quality drafts become evidence
- Claude proposes a new workflow version
- future drafts improve

---

## 4. Product Mental Model

The best way to think about the system is:

- **Trigger** = why something should be created
- **Workflow** = the recipe for making that thing
- **Workflow version** = the current exact recipe revision
- **Brain** = historical memory used during generation and analysis
- **Draft** = one concrete generated output
- **Queue** = where drafts wait for action
- **Review action** = what a human did to a draft
- **Publication record** = what was actually posted

The pipeline is:

```text
trigger -> workflow -> workflow version -> brain retrieval -> generation
-> compliance -> manual or automatic queue -> review/publish
-> publication record -> analytics -> brain update
```

This model should remain true across all platforms.

---

## 5. Full End-To-End Workflow

## 5.1 Daily Operator Workflow

This is what the boss or marketing operator should do in the final app.

1. Open `Home`
2. Review:
   - today’s manual queue count
   - today’s automatic schedule
   - new external triggers
   - any publish failures
3. Open `Manual`
4. Review each all-day item
5. For each draft, choose:
   - `Post Now`
   - `Schedule`
   - `Reject`
   - `Why This Draft?`
   - `Improve Workflow`
6. Open `Automatic`
7. Verify timed workflows are healthy
8. Open `Trigger Feed` if there are new external events
9. Open `Rejected` or `Expired` as needed to inspect history
10. Use Claude to improve workflows based on bad drafts

That is the operator experience the architecture must support.

## 5.2 Calendar Trigger In Manual Mode

Example: “Every Tuesday generate a LinkedIn thought leadership post.”

1. A calendar rule exists.
2. At the start of the day, the scheduler fires it.
3. A `TriggerEvent` is recorded with type `calendar`.
4. The workflow resolver finds the matching workflow.
5. The active workflow version is loaded.
6. The brain retrieves:
   - similar approved posts
   - similar rejected posts
   - brand rules
   - platform rules
   - campaign context
7. Claude generates one or more draft variants.
8. Compliance runs.
9. Passing drafts enter the `Manual` queue.
10. The operator reviews them.
11. If nothing is done by end of day, they become `Expired`.

## 5.3 External Trigger In Manual Mode

Example: a partner event, athlete milestone, or sports event arrives.

1. An external event is ingested.
2. A `TriggerEvent` is recorded with type `external`.
3. The workflow resolver finds the matching workflow.
4. Workflow version and brain context are loaded.
5. Claude generates the draft.
6. Compliance runs.
7. The draft enters the `Manual` queue.
8. The operator can post, schedule, or reject it.

## 5.4 Manual Request Trigger

Example: “Make three posts for transfer portal week.”

1. An operator types a request into the Claude workspace.
2. The system records a `manual_request` trigger event.
3. A matching workflow or ad hoc workflow template is selected.
4. The generation pipeline runs.
5. Drafts appear in `Manual`.

## 5.5 Reject + Improve Workflow

1. Operator rejects a draft.
2. The draft moves to `Rejected`.
3. The draft remains read-only.
4. Operator asks Claude to improve the workflow.
5. Claude receives:
   - the rejected draft
   - workflow metadata
   - workflow version config
   - approved examples
   - rejected examples
   - analytics
6. Claude proposes a new workflow version.
7. Operator previews new sample drafts.
8. Operator activates the new version.
9. The next similar trigger uses the new version.

## 5.6 Automatic Publish

1. Workflow mode is set to `automatic`.
2. Workflow has a defined publish time.
3. Trigger fires.
4. Draft is generated.
5. Compliance passes.
6. Draft is published at the configured time.
7. Publication record is stored.
8. Analytics later update the brain.

---

## 6. System Components

The full product has ten required components.

### 6.1 Trigger Engine

Responsible for:

- firing calendar rules
- ingesting external events
- creating manual-request triggers

Outputs:

- canonical `TriggerEvent` rows

### 6.2 Workflow Resolver

Responsible for:

- finding the right workflow for a trigger
- loading the active workflow version

Outputs:

- `Workflow`
- `WorkflowVersion`

### 6.3 Prompt Assembler

Responsible for:

- combining platform rules
- combining brand rules
- combining workflow version config
- combining retrieved memory

Outputs:

- a structured generation payload for Claude

### 6.4 Generation Pipeline

Responsible for:

- calling Claude
- creating draft variants
- recording generation traces

Outputs:

- `DraftVariant` rows
- generation logs / traces

### 6.5 Compliance Gate

Responsible for:

- deterministic validation
- trademark corrections
- factual claim verification
- platform length and formatting validation

Outputs:

- pass/fail result
- corrected content if safe to auto-correct

### 6.6 Review Queue

Responsible for:

- placing drafts into manual or automatic handling
- storing review actions
- preventing invalid transitions

### 6.7 Publisher Layer

Responsible for:

- publishing to X
- publishing to LinkedIn
- publishing to Instagram
- storing platform result metadata

### 6.8 Content Brain

Responsible for:

- storing approved/rejected/expired/published history
- storing workflow metadata and version links
- storing searchable content memory
- storing analytics signals

### 6.9 Scheduler Worker

Responsible for:

- firing due calendar rules
- expiring untouched manual drafts
- publishing automatic drafts at exact times
- reclaiming stale claimed jobs after crash recovery

### 6.10 Control-Room UI

Responsible for:

- operator workflow
- queue review
- workflow inspection
- history
- analytics
- Claude interaction

---

## 7. Canonical Data Model

The future system should center on canonical control-room tables instead of platform-specific draft tables.

## 7.1 Core Tables

### `workflows`

Represents one content-producing recipe.

Suggested fields:

- `id`
- `slug`
- `name`
- `description`
- `platform`
- `content_type`
- `mode`
- `enabled`
- `active_version_id`
- `fallback_version_id`
- `timezone`
- `created_at`
- `updated_at`

### `workflow_versions`

Immutable workflow definitions.

Suggested fields:

- `id`
- `workflow_id`
- `version_number`
- `config`
- `change_summary`
- `created_by`
- `created_by_type`
- `created_at`

### `calendar_rules`

Time-based triggers.

Suggested fields:

- `id`
- `workflow_id`
- `timezone`
- `day_of_week`
- `hour`
- `minute`
- `all_day_generation`
- `publish_time`
- `enabled`

### `trigger_events`

Canonical record of why a draft exists.

Suggested fields:

- `id`
- `workflow_id`
- `trigger_type`
- `source_kind`
- `source_ref`
- `payload`
- `occurred_at`
- `created_at`

### `content_jobs`

One workflow execution against one trigger.

Suggested fields:

- `id`
- `workflow_id`
- `workflow_version_id`
- `trigger_event_id`
- `status`
- `created_at`
- `started_at`
- `finished_at`

### `draft_variants`

Canonical queue records for all platforms.

Suggested fields:

- `id`
- `content_job_id`
- `workflow_id`
- `workflow_version_id`
- `trigger_event_id`
- `platform`
- `content`
- `content_payload`
- `asset_refs`
- `recommended_post_time`
- `queue_state`
- `expires_at`
- `compliance_result`
- `created_at`
- `updated_at`

### `review_actions`

Human decisions on drafts.

Suggested fields:

- `id`
- `draft_variant_id`
- `action_type`
- `actor_id`
- `notes`
- `created_at`

### `publication_records`

Posted output.

Suggested fields:

- `id`
- `draft_variant_id`
- `platform`
- `platform_post_id`
- `post_url`
- `publish_status`
- `published_at`
- `failure_reason`

### `memory_items`

Canonical searchable history.

Suggested fields:

- `id`
- `source_type`
- `source_status`
- `workflow_id`
- `workflow_version_id`
- `trigger_type`
- `platform`
- `content`
- `metadata`
- `created_at`

### `memory_embeddings`

Optional semantic search support.

Suggested fields:

- `id`
- `memory_item_id`
- `embedding_model`
- `vector`
- `created_at`

### `analytics_snapshots`

Performance signals from live posts.

Suggested fields:

- `id`
- `publication_record_id`
- `observed_at`
- `payload`

## 7.2 Old Tables That Currently Exist

Current repo tables:

- `content_queue`
- `generation_log`
- `linkedin_post`
- `linkedin_generation_log`
- `content_source_target`
- `content_source_snapshot`
- `content_brain_item`
- `content_brain_asset`
- `content_brain_metric_snapshot`

These are useful for current phases, but they are **not** the final canonical control-room model.

### Migration Rule

Agents should:

- leave old tables working while building the new control-room layer
- avoid expanding old table designs further unless needed for safety
- migrate future UI and workflow features to the new canonical tables

---

## 8. Workflow Version Config

`WorkflowVersion.config` is the heart of the workflow editing system.

It should be stored as validated JSONB, not loose arbitrary JSON.

## 8.1 Why JSONB

Workflow versions need flexible structured settings such as:

- prompt additions
- retrieval filters
- tone notes
- CTA preferences
- formatting preferences
- routing behavior
- asset instructions
- timing hints

A rigid column-per-field schema will become painful as workflows evolve.

## 8.2 Required Config Sections

Future agents should validate a structure like:

```json
{
  "prompt": {
    "system_additions": [],
    "user_additions": [],
    "hard_rules": []
  },
  "retrieval": {
    "approved_example_limit": 5,
    "rejected_example_limit": 3,
    "filters": {
      "platform": ["linkedin"],
      "intent": ["brand"]
    }
  },
  "formatting": {
    "target_length": "medium",
    "paragraph_style": "short",
    "hashtag_style": "light"
  },
  "cta": {
    "allowed_types": ["soft_discussion"],
    "avoid_types": ["hard_sell"]
  },
  "routing": {
    "default_mode": "manual"
  },
  "assets": {
    "requires_asset": false,
    "template_family": null
  }
}
```

The exact schema can evolve, but it must remain:

- explicit
- validated
- versioned

---

## 9. UI Architecture

The UI is an internal tool. It should be fast, readable, and operational.

## 9.1 Primary Navigation

Required sidebar views:

- Home
- Manual
- Automatic
- Calendar
- Trigger Feed
- Rejected
- Expired
- Brain / History
- Analytics
- Settings

## 9.2 Manual View

Purpose:

- show all-day drafts that need review

Every card should show:

- platform
- workflow name
- workflow version
- trigger type
- trigger reason
- draft text
- asset preview state
- recommended time

Every card should support:

- `Post Now`
- `Schedule`
- `Reject`
- `Why This Draft?`
- `Improve Workflow`

## 9.3 Automatic View

Purpose:

- show timed, trusted workflows

Every item should show:

- workflow name
- next run time
- publish time
- last result
- mode
- health state

Every item should support:

- `Pause`
- `Resume`
- `Move To Manual`
- `Open Workflow`

## 9.4 Calendar View

Purpose:

- show time-based work

Rules:

- manual items in all-day lane
- automatic items in timed slots

## 9.5 Trigger Feed

Purpose:

- show external events and what they caused

Every item should show:

- event type
- source
- timestamp
- resulting workflow
- resulting draft/job status

## 9.6 Rejected View

Purpose:

- read-only history of wrong drafts

Must show:

- original content
- rejection note
- workflow and version
- trigger that created it

## 9.7 Expired View

Purpose:

- read-only history of drafts that timed out

Must show:

- original content
- workflow
- created_at
- expires_at

## 9.8 Brain / History

Purpose:

- searchable memory of past content

Must filter by:

- platform
- status
- workflow
- trigger type
- date range
- partner
- intent

## 9.9 Workflow Detail View

Purpose:

- inspect and improve a workflow

Must show:

- workflow summary
- mode
- trigger configuration
- active version summary
- version history
- approved examples
- rejected examples
- performance summary
- Claude workflow improvement entry point

---

## 10. Claude’s Role In The Product

Claude is not the dashboard.
Claude is the reasoning and writing layer inside the dashboard.

Claude should be used for:

- content generation
- explaining why a draft exists
- comparing approved vs rejected examples
- proposing workflow improvements
- previewing changed workflow behavior

Claude should not directly own:

- queue persistence
- state transitions
- scheduling
- expiry
- publishing
- audit logging

Those are application responsibilities.

### Important Product Rule

The operator should speak naturally.

They should be able to say:

- “This sounds too corporate.”
- “Use more data and fewer generic hooks.”
- “Make this feel more athlete-facing.”
- “Stop using this CTA style.”

The app should convert that into structured workflow-improvement context for Claude.

---

## 11. Current Implemented Phases And How They Fit

This section explains how current repo code should be interpreted by future agents.

## 11.1 Current X Backend

Relevant files:

- `app/agents/content_writer.py`
- `app/agents/compliance.py`
- `app/api/routes.py`
- `app/models/content.py`
- `app/publishers/*`

What it currently does well:

- generates X content with Claude
- enforces deterministic compliance
- stores draft queue rows
- publishes via adapters

What it does **not** yet do:

- store workflow ids/versions
- store trigger provenance
- support manual vs automatic modes
- support workflow improvement
- support rejected vs expired history semantics

How it fits:

- treat it as the **seed generation/compliance/publish subsystem**
- wrap it behind the future workflow engine
- do not treat `content_queue` as the final queue schema

## 11.2 Current LinkedIn Backend

Relevant files:

- `app/agents/linkedin_writer.py`
- `app/agents/linkedin_compliance.py`
- `app/services/linkedin_pipeline.py`
- `app/api/linkedin_routes.py`
- `app/models/linkedin.py`

What it currently does well:

- generates LinkedIn content
- applies deterministic compliance
- supports manual review tiers

What it does **not** yet do:

- fit the manual-first control-room workflow cleanly
- use canonical workflow tables
- expose trigger provenance
- expose workflow versioning

Important caution:

Current `tier_1` behavior auto-publishes immediately. That conflicts with the product’s manual-first rollout and should not become the long-term control-room behavior.

How it fits:

- treat it as the **LinkedIn content-generation slice**
- integrate it into the future canonical workflow engine
- do not expand its separate queue model as the final design

## 11.3 Current Public Content Brain

Relevant files:

- `app/content_brain/*`
- `app/models/content_brain.py`
- `app/api/routes.py` content-brain endpoints

What it currently does well:

- ingests public web/social content
- stores normalized public content
- exposes a dashboard and retrieval APIs

What it does **not** yet do:

- store workflow-aware approved/rejected/expired marketing history
- connect to workflow generation
- support “Why This Draft?”
- support workflow improvement

How it fits:

- treat it as a **separate public-source ingestion subsystem**
- optionally reuse some of its parsing/storage patterns
- do not confuse it with the final workflow-aware brain

---

## 12. Canonical Phase Plan

This is the high-level implementation order that any agent should follow.

## Phase A: Control-Room Foundation

Goal:

- introduce canonical workflow/trigger/review models without breaking existing phases

Includes:

- new control-room tables
- workflow versions
- trigger events
- canonical draft variants
- review actions

Deliverable:

- a backend that can represent the final workflow model, even if the UI is not finished

## Phase B: Manual Queue Product

Goal:

- make the manual-first operator flow real

Includes:

- queue APIs
- manual queue page
- calendar all-day lane
- rejected history
- expired history

Deliverable:

- operator can review drafts in one place

## Phase C: Brain + Workflow Intelligence

Goal:

- make the workflow-aware brain and workflow editing system real

Includes:

- history search
- approved/rejected/expired storage
- workflow detail view
- Claude-driven workflow improvement
- workflow version preview and activation

Deliverable:

- operator can say “fix the process” and see future drafts improve

## Phase D: Automatic Operations

Goal:

- support trusted workflows publishing at exact times

Includes:

- scheduler worker
- automatic tab
- pause/resume controls
- end-of-day expiry jobs

Deliverable:

- reliable automatic operation for selected workflows

## Phase E: Trigger Expansion

Goal:

- bring in external and partner events cleanly

Includes:

- trigger feed
- webhook/file/manual event ingestion
- external trigger routing

Deliverable:

- external events create drafts with visible provenance

## Phase F: Analytics + Promotion Confidence

Goal:

- use real results to decide which workflows can move to automatic

Includes:

- analytics ingestion
- workflow metrics
- promotion confidence indicators

Deliverable:

- evidence-based manual-to-automatic promotion

## Phase G: Platform Unification And Cleanup

Goal:

- fully unify X, LinkedIn, and Instagram behind the canonical control-room model

Includes:

- generic publisher interface
- migration away from old isolated queue models
- Instagram adapter

Deliverable:

- one product, not three backend slices

## Phase H: Hardening And Handoff

Goal:

- make the system operational for handoff

Includes:

- operator docs
- admin docs
- runbook
- demo data
- launch checklist

Deliverable:

- safe internal handoff to the boss/team

---

## 13. Critical Invariants

Any future agent working on implementation must preserve these invariants.

1. **Every draft must point to a trigger**
   No orphan drafts.

2. **Every draft must point to a workflow and workflow version**
   Otherwise “Why This Draft?” breaks.

3. **Manual and automatic are workflow modes, not just UI filters**
   The backend must enforce mode semantics.

4. **Rejected and expired are distinct**
   Do not merge them.

5. **Workflow improvements create new versions**
   Never silently mutate active workflow behavior without versioning.

6. **Claude never directly mutates queue state**
   Queue state is application-controlled.

7. **Compliance remains deterministic**
   Do not move factual/brand guardrails into vague LLM judgment.

8. **The content brain must include approval outcome and workflow metadata**
   Otherwise it cannot drive future workflow improvement.

9. **The UI must always show trigger provenance**
   If operators cannot see why a draft exists, the product loses trust.

10. **The scheduler must be crash-safe**
   Claimed job staleness and recovery must be handled explicitly.

---

## 14. Implementation Rules For Future Agents

If an agent is using this file to implement the system, it should follow these rules.

### 14.1 Read Order

Read in this order:

1. this file
2. the manual-first design spec
3. the implementation plan
4. current code

### 14.2 Reuse Strategy

Reuse:

- current compliance logic
- current prompt-building patterns
- current platform adapters where possible
- current FastAPI app structure

Do not preserve:

- old queue schemas as the long-term truth
- platform-by-platform fragmentation
- auto-publish defaults that conflict with manual-first rollout

### 14.3 Preferred Technical Direction

Use:

- FastAPI
- SQLAlchemy
- Alembic
- server-rendered control-room UI
- Postgres as source of truth
- a separate DB-backed worker

Avoid:

- building a second frontend unless truly needed
- turning the workflow engine into a pile of route-level logic
- letting the content brain stay separate from workflow state

### 14.4 State Transition Discipline

Every queue/review/publication transition must be explicit and testable.

There should be tests for:

- manual generation
- rejection
- expiry
- scheduling
- automatic publish
- workflow version activation

### 14.5 Review Discipline

Before claiming a phase is complete, an agent should verify:

- schema exists
- API exists
- UI exists if phase requires it
- state transitions are enforced
- tests cover the phase

---

## 15. Verification Checklist For “Full Workflow Works”

The system should only be considered aligned with the intended workflow when all of these are true:

1. A calendar rule can generate a manual all-day draft.
2. An external event can generate a manual draft with visible provenance.
3. A manual request can generate drafts into the same queue.
4. Manual drafts can be posted, scheduled, rejected, or expire.
5. Rejected drafts appear in read-only history.
6. Expired drafts appear in separate read-only history.
7. The UI can explain why a draft exists.
8. Claude can propose a new workflow version based on rejected drafts.
9. The user can preview and activate that new workflow version.
10. The next similar trigger uses the new version.
11. Automatic workflows publish at configured times.
12. The brain can search approved/rejected/expired history by workflow/platform/date.
13. Analytics feed back into the brain and workflow metrics.

If any of the above is missing, the full control-room workflow is not complete yet.

---

## 16. Bottom Line

The final NTangible system is:

- a **manual-first marketing control room**
- backed by **workflows and workflow versions**
- driven by **calendar, external, and manual triggers**
- explained by a **workflow-aware content brain**
- improved by **Claude changing future workflow behavior**
- operated through **one unified dashboard**

That is the architecture future agents should implement toward.
