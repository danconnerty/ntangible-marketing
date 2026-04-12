# NTangible Marketing Control Room — Agent Implementation Brief

> **Purpose:** This is the one-file handoff for any future implementation agent. It is intentionally self-contained. An agent should be able to read this file only, understand the target product, understand the current repo state, understand what to reuse vs replace, and implement the system without needing clarifying questions in normal cases.
>
> **Status:** Canonical implementation brief as of April 6, 2026.
>
> **Instruction to future agents:** Treat this file as the source of truth for product behavior and implementation direction. Do not ask the user clarifying questions unless you hit a true blocker that cannot be resolved from code, tests, config, or the default assumptions in this file.

---

## 1. What This Product Is

NTangible needs one internal app that acts as a **marketing control room**.

This app is not just a content generator and not just a dashboard.

It is one integrated operating system where the operator can:

1. open one app
2. see what content exists for today
3. understand why each draft was generated
4. review drafts manually by default
5. post, schedule, reject, or let manual items expire
6. monitor automatic workflows separately
7. inspect rejected and expired history
8. search the full content brain
9. ask Claude to improve the workflow that creates future drafts

The product is best understood as:

```text
trigger -> workflow -> workflow version -> brain retrieval -> generation
-> compliance -> manual or automatic handling -> publish or history
-> analytics -> brain update -> future workflow improvement
```

---

## 2. Final Product Outcome

The final product should feel like a mix of:

- a queue/inbox for today’s drafts
- a calendar for time-based posting
- a live event feed for outside triggers
- a searchable memory/brain of past content
- a workflow studio where Claude improves future output

The boss should be able to log into one app and do all of the following without opening raw APIs or separate AI chats:

- review today’s manual drafts
- inspect automatic workflows
- understand why a draft exists
- post or schedule approved drafts
- reject bad drafts
- review expired drafts as read-only history
- ask Claude to improve the process that created weak drafts
- search old posts and performance patterns
- promote trusted workflows from manual to automatic later

---

## 3. Locked Product Decisions

These decisions are already made. Do not reopen them unless the user explicitly changes them.

### 3.1 Manual-First Default

All workflows start in `manual` mode.

Meaning:

- drafts are generated
- drafts appear in the `Manual` tab
- a human decides what happens next

### 3.2 Automatic Is Later

Automatic mode is not the default and not the first rollout.

Automatic mode is earned only after a workflow proves reliable.

### 3.3 Two Primary Operator Tabs

The main control surfaces are:

- `Manual`
- `Automatic`

Supporting views still exist, but these two tabs are the core workflow split.

### 3.4 Manual Items Are All-Day

Manual items:

- appear in the manual queue
- appear in the calendar all-day lane
- do not auto-post
- may show a recommended best time badge

### 3.5 Automatic Items Have Exact Times

Automatic items:

- have a configured publish time
- appear in timed calendar slots
- publish through the scheduler at that exact time

### 3.6 Manual Items Expire At End Of Day

If a manual item is not acted on by end of day in the workflow/account timezone:

- it leaves the active queue
- it moves to `Expired`
- it becomes read-only history

### 3.7 Rejected And Expired Are Different

`Rejected` means:

- someone reviewed the draft
- the draft was bad, wrong, or off-strategy

`Expired` means:

- nobody acted on the draft in time
- the draft may still have been fine

These are separate history types and must remain separate in storage, UI, and retrieval.

### 3.8 Claude Improves Workflows, Not One-Off Drafts

The system should not optimize around hand-editing one generated post.

The intended behavior is:

1. a weak draft is rejected
2. the rejected draft becomes evidence
3. Claude studies the workflow and history
4. Claude proposes a new workflow version
5. future similar drafts improve

### 3.9 Trigger Provenance Must Always Be Visible

Every draft must clearly show why it exists.

Allowed trigger origins:

- `calendar`
- `external`
- `manual_request`

### 3.10 The Brain Is Structured Memory, Not Chat History

The brain is not a long prompt with old posts pasted into it.

It is a structured memory system containing:

- approved history
- rejected history
- expired history
- publication history
- workflow and version metadata
- brand rules
- partner rules
- analytics signals

---

## 4. What Exists In The Repo Today

This repo already contains useful backend work, but it does not yet implement the final control-room workflow.

### 4.1 Existing Useful Subsystems

#### X/Twitter pipeline

Reusable files include:

- `app/agents/content_writer.py`
- `app/agents/compliance.py`
- `app/api/routes.py`
- `app/models/content.py`
- `app/publishers/base.py`
- `app/publishers/*`

This already provides:

- Claude generation for X content
- deterministic compliance checks
- publication adapters
- API routes and tests

#### LinkedIn pipeline

Reusable files include:

- `app/agents/linkedin_writer.py`
- `app/agents/linkedin_compliance.py`
- `app/services/linkedin_pipeline.py`
- `app/api/linkedin_routes.py`
- `app/models/linkedin.py`
- `app/publishers/linkedin_*`

This already provides:

- LinkedIn generation
- LinkedIn compliance
- LinkedIn publisher adapters
- LinkedIn-specific persistence and routes

#### Public-content brain

Relevant files include:

- `app/content_brain/*`
- `app/models/content_brain.py`
- `app/api/routes.py`
- public-content-related docs and tests

This already provides:

- ingestion of public content sources
- some retrieval and storage work
- useful research context for later memory enrichment

### 4.2 What Is Missing Today

The repo does **not** yet have:

- a canonical workflow model
- workflow versioning
- canonical trigger events
- one queue spanning all platforms
- manual vs automatic handling modes
- rejected vs expired history as first-class concepts
- a workflow-aware brain
- a scheduler worker for automatic mode
- a control-room UI
- a Claude workflow improvement loop

### 4.3 Important Current Mismatches

These are known implementation mismatches that future agents must correct rather than inherit.

#### LinkedIn currently conflicts with manual-first

The current LinkedIn pipeline was built with tier-based auto-publish assumptions. That conflicts with the manual-first product.

Required correction:

- new canonical workflows start `manual`
- LinkedIn auto-publish behavior must not remain the default control-room behavior

#### Existing “brain” is not yet the final brain

The public-only brain is not the canonical content brain.

It is an auxiliary source of context and historical public content.

The final brain must instead center on:

- approved drafts
- rejected drafts
- expired drafts
- published posts
- workflow versions
- analytics

#### Existing platform-specific tables are not the final queue

`content_queue`, `linkedin_post`, and similar tables are legacy/phase-specific structures.

They may coexist temporarily, but the future system must center on canonical control-room tables.

### 4.4 Current Repo Health Baseline

At the time this brief was written:

- the backend contains real working subsystems
- the repo is not yet a unified control room
- the test suite is close to green but not perfectly clean

Known baseline observations:

- `pytest -q` reported `92 passed, 2 failed`
- the known failing tests were optional publisher import issues in `tests/test_publisher_factory.py`
- optional/live publisher packages should not be allowed to break the default local test path

Future agents should treat the current repo as a useful but transitional baseline, not as a finished foundation.

---

## 5. Canonical Mental Model

Use these nouns consistently in code, docs, routes, and UI.

### Trigger

Why a draft should exist.

Examples:

- Tuesday calendar rule fired
- partner event arrived
- operator requested “make three transfer portal posts”

### Workflow

The recipe for making one kind of content.

Examples:

- Tuesday LinkedIn thought leadership
- FSS leaderboard X data drop
- Alliance commitment Instagram spotlight

### Workflow Version

An immutable revision of a workflow’s generation instructions and retrieval rules.

Examples of what changes between versions:

- hook style
- tone guidance
- CTA preferences
- retrieval filters
- formatting rules
- asset instructions

### Brain

The retrieval layer that supplies historical memory and signals during generation and analysis.

### Content Job

One execution of one workflow against one trigger event.

### Draft Variant

One concrete output candidate from a content job.

### Review Action

A human action taken on a draft, such as:

- `post_now`
- `schedule`
- `reject`
- `expire`

### Publication Record

A permanent record of something that was actually published to a platform.

---

## 6. Full User Workflow

This section defines the behavior the product must support.

### 6.1 Daily Operator Flow

1. Operator opens the app.
2. Home shows:
   - manual queue count
   - automatic queue count
   - new external triggers
   - failures or alerts
   - recently changed workflows
3. Operator opens `Manual`.
4. Operator reviews all-day drafts generated for today.
5. For each manual draft, operator can:
   - `Post Now`
   - `Schedule`
   - `Reject`
   - `Why This Draft?`
   - `Improve Workflow`
6. Operator opens `Automatic` to inspect timed workflows and scheduled publications.
7. Operator opens `Trigger Feed` to inspect outside events and resulting drafts.
8. Operator uses `Rejected` and `Expired` as read-only history views.
9. Operator uses Claude to improve weak workflows.

### 6.2 Calendar Trigger In Manual Mode

Example: every Tuesday, generate a LinkedIn thought-leadership draft.

Flow:

1. calendar rule exists
2. scheduler fires at start of trigger day
3. system records `TriggerEvent(type=calendar)`
4. workflow resolver finds the correct workflow
5. active workflow version is loaded
6. brain retrieval gathers:
   - approved examples
   - rejected examples
   - brand rules
   - platform rules
   - campaign context
7. generation pipeline creates one or more draft variants
8. compliance runs
9. passing drafts enter `Manual`
10. operator posts, schedules, rejects, or does nothing
11. untouched drafts expire at end of day

### 6.3 External Trigger In Manual Mode

Example: partner event, athlete milestone, leaderboard update, sports event.

Flow:

1. external event is ingested
2. system records `TriggerEvent(type=external)`
3. workflow resolver selects workflow
4. active version and brain context load
5. generation runs
6. compliance runs
7. draft enters `Manual`
8. operator reviews it

### 6.4 Manual Request Trigger

Example: operator asks Claude for “three posts for transfer portal week.”

Flow:

1. user creates manual request in app
2. system records `TriggerEvent(type=manual_request)`
3. workflow or template is resolved
4. generation pipeline runs
5. drafts enter `Manual`

### 6.5 Reject And Improve Workflow

This is the key product behavior.

Flow:

1. operator rejects a draft
2. draft moves to `Rejected`
3. rejected draft remains read-only
4. operator asks Claude to improve the workflow
5. Claude receives:
   - rejected draft
   - workflow metadata
   - workflow version config
   - approved examples
   - rejected examples
   - analytics
6. Claude proposes a new inactive workflow version
7. operator previews sample drafts produced from that new version
8. operator activates the new version
9. next similar trigger uses the new version

### 6.6 Automatic Publish Flow

Only for workflows already promoted to automatic.

Flow:

1. workflow is in `automatic`
2. workflow has exact publish time
3. trigger fires
4. draft is generated
5. compliance passes
6. scheduler publishes at configured time
7. publication record is stored
8. analytics later update the brain

---

## 7. UI Structure

The UI should be a practical internal control room, not a polished consumer app.

### 7.1 Main Navigation

Use a left sidebar with:

- `Home`
- `Manual`
- `Automatic`
- `Calendar`
- `Trigger Feed`
- `Rejected`
- `Expired`
- `Brain / History`
- `Analytics`
- `Workflows`
- `Settings`

### 7.2 Top-Level Layout

Use:

- left sidebar navigation
- top status bar
- main content panel
- right-side detail drawer or modal
- embedded Claude input / workflow assistant area

### 7.3 Home

Home should show summary widgets for:

- manual count today
- automatic count today
- new external triggers
- failed posts
- workflows recently changed
- upcoming automatic posts

### 7.4 Manual Tab

This is the most important first UI.

Each manual draft card should show:

- platform
- workflow name
- trigger provenance
- trigger reason summary
- full or truncated content preview
- asset/media preview if relevant
- recommended best time
- compliance status
- creation time

Actions on each manual draft:

- `Post Now`
- `Schedule`
- `Reject`
- `Why This Draft?`
- `Improve Workflow`

### 7.5 Automatic Tab

Each automatic workflow row/card should show:

- workflow name
- platform
- next trigger time
- publish time
- mode
- last publication status
- health or failure badge

Actions:

- `Pause`
- `Resume`
- `Move To Manual`

### 7.6 Calendar

This view must follow the locked timing rules:

- manual items in all-day lane
- automatic items in exact time slots

### 7.7 Trigger Feed

This is the live event view for outside signals.

Each entry should show:

- event source
- event type
- partner if applicable
- creation time
- resulting job status
- linked draft if one was created

### 7.8 Rejected

Read-only history.

Each entry should show:

- rejected draft content
- rejection note
- workflow and workflow version
- trigger source
- rejection time

### 7.9 Expired

Read-only history.

Each entry should show:

- expired draft content
- trigger source
- workflow and version
- expiry timestamp

### 7.10 Brain / History

Searchable content memory.

Filters should include:

- platform
- workflow
- trigger type
- status
- date range
- partner
- intent

### 7.11 Workflow Detail / Workflow Studio

This is where the operator understands and improves workflows.

It should show:

- current mode
- trigger config
- active version summary
- version history
- approval / rejection / expiration trends
- representative approved examples
- representative rejected examples
- Claude improvement actions
- preview and activate flow for new versions

---

## 8. Canonical Data Model

The future system should center on new canonical control-room tables, not platform-specific draft tables.

### 8.1 Required Core Tables

#### `workflows`

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

#### `workflow_versions`

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

The `config` field should be validated JSONB, not arbitrary JSON.

Required logical sections inside `config`:

- `prompt`
- `retrieval`
- `formatting`
- `routing`
- `timing`
- `assets`
- `cta`

#### `calendar_rules`

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
- `next_fire_at`
- `claimed_by`
- `claimed_at`

#### `trigger_events`

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

#### `content_jobs`

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

#### `draft_variants`

Canonical queue rows for all platforms.

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
- `prompt_snapshot`
- `retrieval_snapshot`
- `generation_trace`
- `created_at`
- `updated_at`

#### `review_actions`

Human decisions on drafts.

Suggested fields:

- `id`
- `draft_variant_id`
- `action_type`
- `actor`
- `notes`
- `created_at`

#### `publication_records`

Permanent record of published content.

Suggested fields:

- `id`
- `draft_variant_id`
- `platform`
- `platform_post_id`
- `post_url`
- `published_at`
- `publish_result`

#### `memory_items`

Canonical searchable memory records.

Suggested fields:

- `id`
- `source_type`
- `source_id`
- `platform`
- `workflow_id`
- `workflow_version_id`
- `trigger_type`
- `status`
- `title`
- `content_text`
- `metadata`
- `created_at`

#### `memory_embeddings`

Embedding table for semantic search.

Suggested fields:

- `id`
- `memory_item_id`
- `embedding`
- `model`
- `created_at`

#### `analytics_snapshots`

Post-publication performance records.

Suggested fields:

- `id`
- `publication_record_id`
- `captured_at`
- `metrics`

### 8.2 Optional Supporting Tables

Add as needed:

- `assets`
- `partners`
- `brand_rules`
- `template_mappings`

### 8.3 Required State Semantics

Draft states must support at least:

- `draft`
- `manual_pending`
- `automatic_pending`
- `scheduled`
- `published`
- `rejected`
- `expired`
- `failed`

Keep `rejected` and `expired` distinct everywhere.

---

## 9. System Components And Responsibilities

The final product has ten required components.

### 9.1 Trigger Engine

Responsible for:

- firing calendar rules
- ingesting external events
- creating manual-request triggers

Output:

- canonical `TriggerEvent` rows

### 9.2 Workflow Resolver

Responsible for:

- finding the correct workflow for a trigger
- loading the active workflow version

Output:

- `Workflow`
- `WorkflowVersion`

### 9.3 Prompt Assembler

Responsible for:

- combining brand rules
- combining platform rules
- combining workflow config
- combining retrieved memory

Output:

- structured generation payload for Claude

### 9.4 Generation Pipeline

Responsible for:

- calling Claude
- creating draft variants
- recording traces

Output:

- `DraftVariant` rows
- prompt and retrieval snapshots

### 9.5 Compliance Gate

Responsible for:

- deterministic validation
- trademark corrections
- factual claim checks
- platform length and formatting checks

Output:

- pass/fail result
- safe corrected content when auto-correction is allowed

### 9.6 Review Queue

Responsible for:

- placing drafts into manual or automatic handling
- enforcing valid state transitions
- recording review actions

### 9.7 Publisher Layer

Responsible for:

- publishing to X
- publishing to LinkedIn
- publishing to Instagram
- storing platform result metadata

This layer must use a generic publishing contract, not tweet-specific naming.

### 9.8 Content Brain

Responsible for:

- storing approved, rejected, expired, and published history
- storing workflow and version links
- storing searchable memory
- storing analytics signals

### 9.9 Scheduler Worker

Responsible for:

- firing due calendar rules
- expiring untouched manual drafts
- publishing automatic drafts at exact times
- reclaiming stale claimed jobs after crashes

### 9.10 Control-Room UI

Responsible for:

- the operator workflow
- queue review
- workflow inspection
- history
- analytics
- embedded Claude interaction

---

## 10. Default Technical Approach

Unless there is a strong codebase-specific reason otherwise, use the following implementation choices.

### 10.1 Backend

- continue with Python + FastAPI
- continue with SQLAlchemy + Alembic + Postgres
- keep the app as a modular monolith

### 10.2 UI

- server-rendered HTML through FastAPI/Jinja2
- HTMX for actions and partial refreshes
- light JavaScript only where needed

Do not introduce a separate frontend framework unless the user explicitly asks for it.

### 10.3 Scheduler

Use a dedicated DB-polling worker process with Postgres as the source of truth.

Preferred behavior:

- `SELECT ... FOR UPDATE SKIP LOCKED`
- claimed timestamps
- reclaim stale claims
- explicit worker entrypoint script

### 10.4 Memory Search

Use:

- metadata filters first
- pgvector second

Do not block the initial control-room experience on embeddings.

### 10.5 Publishers

Generalize the publishing contract early so all platforms can sit behind one queue model.

Required direction:

- rename tweet-specific methods to generic publish methods
- rename `tweet_id` style fields to `platform_post_id`
- rename `tweet_url` style fields to `post_url`

### 10.6 Workflow Config

Use validated JSONB for workflow version config.

Do not scatter workflow settings across many columns too early.

---

## 11. How Existing Phases Map Into The Final Workflow

This is the most important migration guidance for future agents.

### 11.1 Existing Phase: X Content Writer + X Posting

Current role:

- useful generation pipeline
- useful compliance logic
- useful publisher adapters

Future role:

- becomes the X-specific implementation behind the canonical workflow engine
- no longer acts as the final system of record for queue behavior

Required integration rule:

- wrap, adapt, and reuse this logic
- do not let the old X-only path remain the permanent primary control model

### 11.2 Existing Phase: LinkedIn Pipeline

Current role:

- useful LinkedIn-specific writing, compliance, and publisher work

Future role:

- becomes the LinkedIn-specific implementation behind the canonical workflow engine

Required correction:

- remove the assumption that LinkedIn tiering drives final queue behavior
- manual-first workflow rules override old auto-publish defaults

### 11.3 Existing Phase: Public-Only Content Brain

Current role:

- good auxiliary historical/public-source ingestion

Future role:

- optional enrichment source for the final brain

Important limitation:

- it is not the canonical control-room memory by itself

The final brain must prioritize internal workflow history over public-source history.

### 11.4 Missing Phase: Canonical Control-Room Foundation

This is the first major missing implementation layer.

It introduces:

- workflows
- workflow versions
- trigger events
- content jobs
- draft variants
- review actions

### 11.5 Missing Phase: Manual Queue Product

This is the first user-visible target.

It introduces:

- Manual tab
- all-day calendar behavior
- post / schedule / reject actions
- rejected history
- expired history

### 11.6 Missing Phase: Workflow Intelligence

This introduces:

- final brain/history retrieval
- Why This Draft
- Improve Workflow
- preview and activate new versions

### 11.7 Missing Phase: Automatic Operations

This introduces:

- automatic tab
- exact publish times
- scheduler worker
- pause/resume/move-to-manual controls

### 11.8 Missing Phase: Trigger Expansion

This introduces:

- partner/webhook/file event ingestion
- Trigger Feed
- audit link from trigger to resulting drafts

### 11.9 Missing Phase: Analytics And Promotion Confidence

This introduces:

- publication analytics
- workflow health metrics
- evidence for moving workflows from manual to automatic

---

## 12. Canonical Delivery Order

Follow this order unless the user explicitly changes priorities.

### Phase A: Canonical Schema

Create:

- `app/models/workflow.py`
- `app/models/trigger.py`
- `app/models/review.py`
- updates to `app/models/__init__.py`
- Alembic migration for new tables

Goal:

- establish the future source of truth without deleting old tables

### Phase B: Workflow And Trigger Services

Create:

- `app/services/workflow_engine.py`
- `app/services/trigger_engine.py`
- `app/services/prompt_assembler.py`

Goal:

- route all future generation through one workflow-aware seam

### Phase C: Review Queue API

Create:

- `app/services/review_queue.py`
- `app/api/control_room_routes.py`
- `app/api/history_routes.py`

Goal:

- make the queue behavior real before UI work

### Phase D: UI Shell

Create:

- `app/web/routes.py`
- `app/web/templates/base.html`
- `app/web/templates/home.html`
- `app/static/css/control_room.css`
- `app/static/js/control_room.js`

Goal:

- establish the operator shell and navigation

### Phase E: Manual-First Views

Create:

- `manual.html`
- `calendar.html`
- `rejected.html`
- `expired.html`

Goal:

- deliver the first demoable operator experience

### Phase F: Brain And Workflow Studio

Create:

- `app/models/memory.py`
- `app/services/memory_retrieval.py`
- `app/services/workflow_editor.py`
- `app/api/workflow_routes.py`
- `brain.html`
- `workflow_detail.html`

Goal:

- make “Why This Draft?” and “Improve Workflow” real

### Phase G: Scheduler And Automatic Mode

Create:

- `app/services/scheduler.py`
- worker entrypoint script
- `automatic.html`

Goal:

- add timed publication and end-of-day expiry

### Phase H: External Trigger Feed

Create:

- `app/api/trigger_routes.py`
- `trigger_feed.html`

Goal:

- make outside events visible and traceable

### Phase I: Analytics

Create:

- `app/models/analytics.py`
- `app/services/analytics_ingest.py`
- `analytics.html`

Goal:

- close the feedback loop and support promotion confidence

### Phase J: Platform Cleanup

Modify:

- `app/publishers/*`
- `app/api/routes.py`
- existing X and LinkedIn layers

Goal:

- converge old platform-specific paths behind the canonical control-room architecture

### Phase K: Hardening And Handoff

Create:

- operator guide
- admin guide
- runbook
- demo seed data

Goal:

- make the app usable by people other than the implementation agent

---

## 13. Implementation Rules For Future Agents

These rules exist to avoid drift.

### 13.1 Preserve Existing Working Code Unless It Blocks The Architecture

Reuse useful generation/compliance/publisher code.

Do not rewrite subsystems just because the architecture is evolving.

### 13.2 Prefer Additive Migration First

New canonical tables and routes should coexist with old ones until the canonical path is proven.

### 13.3 Do Not Collapse Rejected And Expired

Never model them as the same status with different labels.

### 13.4 Do Not Hide Trigger Provenance

Every draft must be traceable back to a trigger event.

### 13.5 Do Not Make Claude A Magical Black Box

Record:

- prompt snapshot
- retrieval snapshot
- workflow version used
- compliance result
- change summary for workflow edits

Without those, `Why This Draft?` and `Improve Workflow` are not trustworthy.

### 13.6 Do Not Let Old Platform Logic Dictate The Final Queue Model

Platform-specific phases are inputs into the final architecture, not the architecture itself.

### 13.7 Keep The UI Internal-Tool Simple

Prioritize:

- speed
- readability
- clear states
- clear provenance
- reliable actions

Do not turn this into a marketing site.

### 13.8 Timezone Semantics Are Not Optional

Expiry and calendar behavior must use workflow/account timezone, not server default time.

---

## 14. Default Assumptions When Something Is Unspecified

Future agents should use these defaults instead of asking the user routine questions.

### 14.1 Product Defaults

- default new workflow mode: `manual`
- manual drafts: all-day items
- automatic drafts: timed items
- manual expiry: end of same calendar day in workflow timezone
- expired items: read-only history
- rejected items: read-only history
- workflow changes from Claude: create new inactive version first
- activation of new workflow version: explicit operator action

### 14.2 Architecture Defaults

- stay inside FastAPI app
- use Jinja2 + HTMX for UI
- use Postgres as source of truth
- use additive migrations
- keep old routes alive until canonical replacements exist

### 14.3 Memory Defaults

- approved, rejected, expired, and published records all become memory candidates
- metadata filters ship before semantic search
- public-source brain is secondary, not primary

### 14.4 Testing Defaults

- every new service gets focused unit tests
- every new route gets API tests
- every new UI view gets smoke tests
- scheduler behavior gets deterministic tests with mocked time or fixtures

### 14.5 Publishing Defaults

- use mock publishers for tests and staging flows unless real credentials are explicitly configured

---

## 15. Known Risks And How To Handle Them

### 15.1 pgvector Complexity

Do not block core workflow delivery on embeddings.

Fallback:

- ship metadata-only search first
- add embeddings once canonical history exists

### 15.2 Workflow Config Drift

If `workflow_versions.config` becomes unstructured, workflow editing will become unreliable.

Mitigation:

- validate config through a strict Pydantic model early

### 15.3 Old/New Table Coexistence

There will be a transition period.

Mitigation:

- define clear source-of-truth rules by route
- import or mirror needed history into canonical memory
- avoid deleting old tables until canonical flow is proven

### 15.4 Scheduler Reliability

Mitigation:

- use claim fields
- use stale-claim reclaim logic
- record worker activity

### 15.5 Optional Publisher Dependencies

The current repo already shows optional dependency issues around publisher imports.

Mitigation:

- isolate optional imports behind factories
- keep tests green without requiring all live publisher packages

---

## 16. Acceptance Criteria For “This Works”

The implementation is only successful when all of the following are true.

### 16.1 Operator Workflow

- operator can log into one app
- operator can understand the day’s work from Home and Manual
- every draft shows why it was generated
- manual drafts can be posted, scheduled, rejected, or allowed to expire

### 16.2 History Behavior

- rejected and expired are separate, read-only histories
- rejected drafts include rejection notes
- expired drafts retain provenance and timestamps

### 16.3 Workflow Intelligence

- Why This Draft explains workflow, version, trigger, and retrieval basis
- Improve Workflow creates a new workflow version
- operator can preview and activate a new version
- next similar draft uses the activated version

### 16.4 Calendar And Timing

- manual items render in all-day lane
- automatic items render in exact time slots
- manual items expire correctly at end of day
- automatic items publish at exact configured time

### 16.5 Trigger Visibility

- external triggers appear in Trigger Feed
- each generated draft can point back to its trigger

### 16.6 Brain / Search

- approved, rejected, expired, and published content are searchable
- results can be filtered by platform, workflow, trigger type, and date

### 16.7 Platform Behavior

- X and LinkedIn can operate through the canonical control-room path
- Instagram can at minimum use a mock/placeholder publisher path until real adapter work is complete

---

## 17. Recommended Verification Checklist

Before calling the work complete, verify:

1. `pytest` passes for old and new tests
2. `alembic upgrade head` succeeds cleanly
3. manual walkthrough works:
   - create workflow
   - fire calendar trigger
   - inspect manual queue
   - post or reject draft
   - verify history behavior
4. workflow improvement works:
   - reject draft
   - ask Claude to improve workflow
   - preview new version
   - activate new version
   - generate next draft from same workflow
5. scheduler works:
   - calendar rule fires
   - manual drafts expire at end of day
   - automatic drafts publish at configured time
6. brain search works:
   - find approved content
   - find rejected content
   - find expired content
   - find workflow-specific history
7. UI works at the control-room path with all major views rendering

---

## 18. If You Are A Future Agent, Start Here

Read this file fully once.

Then follow this execution order:

1. inspect existing code paths for X, LinkedIn, publishers, and current brain
2. implement the canonical schema
3. implement workflow and trigger services
4. implement the review queue API
5. implement the web shell and manual views
6. implement brain/history retrieval and workflow studio
7. implement scheduler and automatic mode
8. implement trigger feed and analytics
9. unify old platform-specific paths behind the canonical flow
10. harden, document, and verify end to end

When uncertain, prefer the choice that:

- preserves the manual-first product
- preserves provenance and traceability
- improves future drafts instead of one-off edits
- keeps the system observable and testable
- moves old platform-specific logic behind the canonical workflow model

This file is intended to be sufficient on its own.
