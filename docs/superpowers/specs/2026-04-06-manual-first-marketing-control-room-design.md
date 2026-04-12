# NTangible Manual-First Marketing Control Room — Design Spec

**Date:** 2026-04-06  
**Status:** Proposed  
**Approach:** Extend the existing FastAPI modular monolith with a control-room UI, unified workflow system, trigger engine, and structured content brain.

---

## Overview

Build one internal app that lets NTangible run marketing from a single place:

- generate content for X, LinkedIn, and Instagram
- show exactly why each post was generated
- review everything manually by default
- promote trusted workflows into automatic publishing later
- keep a searchable history of approved, rejected, and expired content
- let Claude improve the workflow that creates future drafts instead of editing single posts by hand

This app is not “Claude plus a few buttons.” It is a **marketing control room** with Claude embedded as the writing and workflow-improvement layer.

The boss should be able to:

1. open the app
2. see today’s manual queue and automatic schedule
3. understand which posts came from the calendar vs outside events
4. post, schedule, reject, or pause content
5. use Claude to improve the workflow that produced bad drafts
6. review the full content brain and monitor results

---

## Product Decisions Locked In

These decisions override the automation-first posture in the original blueprint for v1 rollout:

- **Manual-first by default**
  Every new workflow starts in `manual` mode.

- **Automatic is opt-in**
  A workflow becomes automatic only after the team trusts it.

- **Trigger provenance is always visible**
  Every draft shows whether it came from a calendar rule, an external event, or a direct manual request.

- **Manual items are all-day items**
  They do not have a forced publish time. They can show a recommended time, but they wait for human action.

- **Automatic items require a specific publish time**
  They live in the timed schedule and publish without waiting for review.

- **Unreviewed manual items expire at end of day**
  Expired items move to read-only history and do not re-enter the queue.

- **Rejected items are read-only history**
  They are not edited in place.

- **Claude improves workflows, not one-off posts**
  The system should learn by updating workflow versions, not by repeatedly hand-editing individual drafts.

---

## What The Product Is

The system has four visible operator surfaces:

1. **Manual**
   The all-day review desk for drafts waiting on human action.

2. **Automatic**
   The timed publishing area for trusted workflows.

3. **Control Views**
   Calendar, trigger feed, rejected history, expired history, brain/history, analytics, settings.

4. **Claude Workspace**
   Embedded assistant for querying the brain, explaining drafts, and improving workflows.

The app is one operational system made of these backend parts:

- workflow registry
- workflow versioning
- trigger engine
- generation pipeline
- compliance gate
- review queue
- publishing adapters
- content brain
- analytics ingestion
- scheduler/worker
- admin UI

---

## Users And Roles

### 1. Boss / Admin

Primary operator.

Needs to:

- review manual drafts
- inspect automatic workflows
- approve promotion from manual to automatic
- pause workflows
- query Claude
- review rejected and expired history
- inspect analytics
- change workflow behavior

### 2. Marketing Operator

Optional secondary operator.

Needs to:

- review and post drafts
- reject drafts
- add notes for Claude
- schedule approved drafts
- monitor trigger feed

### 3. System Worker

Background worker role.

Needs to:

- fire due calendar rules
- expire stale manual drafts
- publish automatic drafts at exact times
- ingest external triggers
- pull analytics

---

## Recommended Technical Shape

Because the repo already contains a Python/FastAPI backend and Phase 1 X pipeline, the fastest integrated path is:

- keep **FastAPI** as the main application and API
- keep **SQLAlchemy + Alembic + Postgres** as the system of record
- keep **Anthropic/Claude** as the generation and workflow-improvement model
- add a **server-rendered admin UI** inside FastAPI for the control room
- add a separate **scheduler/worker process** in the same Python codebase
- reuse and expand the existing platform adapters for X, LinkedIn, and Instagram
- add a structured **content brain** backed by Postgres and pgvector

This is the best fit for the current repo because it avoids splitting the system across unrelated stacks too early.

### Why Not Start With A Separate Frontend Framework?

The dashboard is an internal operator app, not a public marketing site. A FastAPI-rendered control room with HTMX/Alpine or light progressive JavaScript is enough for:

- queue views
- cards and detail drawers
- calendar and trigger feed
- workflow detail pages
- Claude chat drawer

If NTangible later wants a richer product surface, the API can remain stable and a separate frontend can be added later.

---

## High-Level Architecture

```text
Calendar Rules ----\
External Events ----> Trigger Engine ---> Workflow Resolver ---> Generation Pipeline
Manual Requests ----/                              |                    |
                                                   |                    v
                                                   |             Compliance Gate
                                                   |                    |
                                                   v                    v
                                           Workflow Version        Draft Variants
                                                   |                    |
                                                   |                    v
                                                   |          Manual Queue / Automatic Queue
                                                   |                    |
                                                   v                    v
                                              Content Brain <--- Publications / Analytics
                                                   ^
                                                   |
                                           Claude Workflow Editor
```

### System Services

1. **Trigger Engine**
   Decides when work should happen.

2. **Workflow Resolver**
   Chooses the right workflow and version for a trigger.

3. **Generation Pipeline**
   Builds prompts, retrieves examples from the brain, and asks Claude to generate structured content.

4. **Compliance Gate**
   Applies deterministic checks before anything reaches the queue.

5. **Queue Manager**
   Places drafts into manual or automatic handling.

6. **Publisher**
   Talks to X, LinkedIn, and Instagram APIs.

7. **Brain**
   Stores and retrieves historical posts, workflow guidance, and feedback.

8. **Workflow Editor**
   Lets Claude propose changes to workflow definitions and prompt inputs.

9. **Analytics Service**
   Pulls and stores performance signals for learning and reporting.

10. **Admin UI**
    The operator-facing control room.

---

## UI Information Architecture

### Global Layout

- **Left sidebar**
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

- **Top bar**
  - workspace title
  - global search
  - “Ask Claude” input
  - platform health badges
  - global pause / kill switch

- **Main content area**
  - queue cards, tables, detail views, timeline views

- **Right detail drawer**
  - draft details
  - trigger details
  - asset preview
  - workflow notes
  - Claude explanation / workflow actions

### Home Screen

Purpose: one place to understand “what is happening today.”

Widgets:

- manual queue count
- automatic posts due today
- new external triggers
- failed publications
- platform health
- top-performing recent posts
- workflows recently changed

### Manual Tab

Purpose: all-day review desk.

Each card shows:

- trigger type: `calendar`, `external`, or `manual_request`
- workflow name
- platform
- content type
- generated timestamp
- recommended post time
- status badge
- short content preview
- asset preview badge if present

Primary actions:

- `Post Now`
- `Schedule`
- `Reject`
- `Why This Draft?`
- `Improve Workflow`

### Automatic Tab

Purpose: view and control trusted workflows.

Each row/card shows:

- workflow name
- platform
- trigger type
- next run time
- publish time
- last draft result
- last published result
- error state if any

Primary actions:

- `Pause`
- `Move To Manual`
- `Open Workflow`
- `View Last Post`

### Calendar View

Purpose: view time-based rules and due content.

Rules:

- manual items appear in the **all-day lane**
- automatic items appear in exact **time slots**

Each calendar item should show:

- workflow name
- platform
- status
- mode
- trigger origin

### Trigger Feed

Purpose: live/event-driven visibility.

Shows:

- partner API events
- uploaded CSV ingestions
- sports calendar events
- competitor or news events
- manual content requests

Each trigger entry should show:

- event type
- source system
- related partner or campaign
- event timestamp
- whether a draft was generated
- resulting queue item status

### Rejected View

Purpose: read-only history of bad drafts and why they were rejected.

Each item shows:

- original draft
- workflow name and version
- trigger that created it
- rejection note
- who rejected it
- timestamp
- link to `Improve Workflow`

### Expired View

Purpose: read-only history of manual items that aged out.

Each item shows:

- original draft
- workflow name
- trigger
- generated date
- expiry timestamp
- whether it ever received any notes

### Brain / History

Purpose: search the entire content memory.

Search facets:

- platform
- status: approved / rejected / expired / published
- workflow
- trigger type
- partner
- intent
- content pillar
- date range
- high-performing only

Results should show:

- content preview
- performance snapshot
- associated workflow version
- tags and trigger context

### Workflow Detail / Studio

Purpose: inspect and improve a workflow.

Sections:

- workflow summary
- current mode: manual or automatic
- trigger configuration
- publish timing rules
- current version summary
- version history
- recent acceptance rate
- recent rejection reasons
- representative approved outputs
- representative rejected outputs
- button to ask Claude to improve the workflow

### Analytics

Purpose: see what worked and what did not.

Metrics:

- posts published by platform
- approval vs rejection rate
- expiration rate
- engagement by workflow
- best hooks and CTAs
- best performing trigger types
- workflow confidence trends

---

## End-To-End User Workflows

## 1. Calendar Trigger In Manual Mode

Example: Tuesday LinkedIn thought leadership.

1. A calendar rule exists for Tuesday.
2. At the start of Tuesday, the scheduler fires the rule.
3. The trigger engine creates a `trigger_event`.
4. The workflow resolver selects the matching workflow and active version.
5. The generation pipeline retrieves:
   - relevant approved posts
   - relevant rejected posts
   - brand rules
   - platform rules
   - campaign context
6. Claude generates the draft.
7. Compliance runs.
8. The passing draft enters the **Manual** tab as an all-day item.
9. The operator chooses `Post Now`, `Schedule`, or `Reject`.
10. If untouched by day end, the item becomes `expired`.

## 2. External Trigger In Manual Mode

Example: Alliance commitment event.

1. Partner event arrives via webhook or ingestion.
2. Trigger feed records the event.
3. Workflow resolver selects the partner workflow.
4. Generation pipeline retrieves partner rules and similar content.
5. Claude generates the draft and any attached asset brief.
6. Compliance runs.
7. The draft appears in the **Manual** tab immediately.
8. Operator posts, schedules, or rejects it.

## 3. Manual Request

Example: “Make three posts for transfer portal week.”

1. Boss enters the request in the Claude box.
2. Claude asks the backend for relevant memory and workflow suggestions.
3. The system creates a manual trigger event.
4. Drafts are generated and appear in the Manual queue.
5. Operator acts on them like any other draft.

## 4. Reject + Improve Workflow

1. Operator rejects a draft.
2. Draft moves to `rejected` history.
3. Operator opens `Improve Workflow`.
4. Claude receives:
   - the rejected draft
   - the active workflow version
   - similar approved examples
   - similar rejected examples
   - brand rules
   - analytics
5. Claude proposes a structured workflow patch.
6. User previews sample outputs using the proposed version.
7. User activates the new version.
8. The next similar draft uses the new version.

## 5. Automatic Publish

1. Workflow is marked automatic and given a publish time.
2. Trigger fires.
3. Draft is generated and passes compliance.
4. Scheduler publishes at the exact configured time.
5. Result is stored in publication history.
6. Analytics come back later and update the brain.

---

## Workflow Model

A **workflow** is the recipe for producing a specific type of content.

Examples:

- Tuesday LinkedIn thought leadership
- Alliance commitment post
- FSS regional leaderboard
- Friday X data drop
- Monthly newsletter draft

Each workflow contains:

- name
- description
- mode: `manual` or `automatic`
- platform
- content type
- trigger type
- routing rules
- active version
- fallback version
- timing configuration
- partner/campaign scope if relevant

### Workflow Version

A workflow version is immutable once activated.

It stores:

- system prompt additions
- retrieval filters
- approved example IDs
- rejected example IDs to avoid
- platform formatting rules
- CTA preferences
- tone notes
- asset instructions
- version note / change summary
- author: human or Claude

The app should never silently mutate a live workflow. Claude must create a new version, and the user chooses whether to activate it.

---

## Trigger Model

Triggers fall into three categories:

### 1. Calendar

Time-based.

Examples:

- every Tuesday
- every first Monday of the month
- weekdays at 8 AM

### 2. External

Event-based.

Examples:

- athlete commitment
- assessment milestone
- partner event results
- sports calendar event
- competitor/news signal

### 3. Manual Request

Human-created request from the UI.

Every draft must link back to exactly one trigger event.

---

## Draft State Model

Canonical states:

- `generated`
- `manual_ready`
- `scheduled_manual`
- `automatic_ready`
- `publishing`
- `published`
- `failed`
- `rejected`
- `expired`

Key rules:

- manual drafts expire at day end if untouched
- rejected and expired are read-only
- automatic items require a publish timestamp
- workflow changes affect future drafts only

---

## Content Brain

The brain is not chat memory. It is a structured content memory system.

### Brain Buckets

1. **Approved Content Memory**
   Published and accepted posts, blog drafts, partner packages, newsletters.

2. **Rejected Feedback Memory**
   Rejected drafts plus rejection reasons.

3. **Expired History**
   Drafts that timed out without action.

4. **Workflow Memory**
   Active workflow definitions, old versions, rules, and change logs.

5. **Brand Knowledge**
   Approved claims, brand rules, partner restrictions, template rules.

6. **Analytics Memory**
   Best hooks, best CTAs, performance patterns, workflow confidence.

### What Gets Stored For Each Post

- platform
- workflow
- workflow version
- trigger type and source
- full content text
- asset references
- intent
- content type
- approval outcome
- publication outcome
- analytics snapshot
- human notes

### Retrieval Strategy

Every generation should first retrieve:

- strong approved examples
- related rejected examples
- relevant brand rules
- relevant partner rules
- recent analytics patterns

The retrieval layer should support:

- metadata filtering
- full-text search
- semantic search via embeddings

---

## Claude Workflow Improvement Model

The Claude interaction should not be “edit this post.”
It should be “improve the workflow that made this post.”

### Inputs To Claude

- rejected draft or low-performing approved draft
- workflow definition and active version
- recent workflow metrics
- related approved examples
- related rejected examples
- brand/platform constraints

### Claude Output

Claude should return a structured proposal such as:

- what changed
- why it changed
- which parts of the workflow are affected
- a patch object or diff for the workflow version
- 1 to 3 preview drafts generated under the proposed new version

### Required Operator Review

Before activation, the operator should be able to see:

- summary of changes
- before vs after preview
- version note
- scope of effect

### Activation Rule

Only after explicit approval does the new version become active.

---

## Data Model

The integrated app should introduce a canonical control-room schema above the current platform-specific models.

### New Core Tables

- `workflows`
- `workflow_versions`
- `calendar_rules`
- `trigger_events`
- `content_jobs`
- `draft_variants`
- `review_actions`
- `publication_records`
- `assets`
- `feedback_notes`
- `memory_items`
- `memory_embeddings`
- `analytics_snapshots`
- `workflow_metrics`
- `partner_sources`
- `ingestion_events`

### Transitional Rule

Existing tables like `content_queue` and `linkedin_post` can remain during migration, but the control room should move toward one generic queue model instead of duplicating logic per platform forever.

---

## Recommended File Structure

### Backend

- `app/models/workflow.py`
- `app/models/trigger.py`
- `app/models/review.py`
- `app/models/memory.py`
- `app/models/analytics.py`
- `app/services/workflow_engine.py`
- `app/services/trigger_engine.py`
- `app/services/generation_pipeline.py`
- `app/services/review_queue.py`
- `app/services/workflow_editor.py`
- `app/services/memory_retrieval.py`
- `app/services/scheduler.py`
- `app/services/analytics_ingest.py`
- `app/api/control_room_routes.py`
- `app/api/workflow_routes.py`
- `app/api/trigger_routes.py`
- `app/api/analytics_routes.py`

### Admin UI

- `app/web/routes.py`
- `app/web/templates/base.html`
- `app/web/templates/home.html`
- `app/web/templates/manual.html`
- `app/web/templates/automatic.html`
- `app/web/templates/calendar.html`
- `app/web/templates/trigger_feed.html`
- `app/web/templates/workflow_detail.html`
- `app/web/templates/rejected.html`
- `app/web/templates/expired.html`
- `app/web/templates/brain.html`
- `app/web/templates/analytics.html`
- `app/static/css/control_room.css`
- `app/static/js/control_room.js`

---

## Integration Points

### Existing Repo Components To Reuse

- `app.agents.content_writer`
- `app.agents.compliance`
- `app.publishers.*`
- existing X models and routes as seed behavior
- existing LinkedIn planning docs

### New Integrations To Add

- Instagram publisher and formatter
- scheduler/worker process
- embeddings provider for brain search
- partner webhook ingestion
- analytics pullers

---

## Out Of Scope For The First Integrated Release

- public-facing marketing site redesign
- advanced multi-user permission matrix beyond admin/operator basics
- full CRM / lead nurture automation
- auto-commenting on external posts
- full creative/video editing suite

---

## Definition Of Done For The Boss

The product is ready to hand off when the boss can:

1. log into one app
2. see today’s manual queue and automatic schedule
3. understand why every post exists
4. post, schedule, reject, or pause content
5. review rejected and expired history
6. search past posts and examples in the brain
7. ask Claude to improve workflows
8. promote trusted workflows into automatic mode
9. monitor publishing results and platform health

If those nine things work reliably, the app matches the intended operator experience.
