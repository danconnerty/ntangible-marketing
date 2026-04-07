# Phase 7: Scheduler And Automatic Mode — Design Spec

**Date:** 2026-04-06  
**Status:** Draft for review  
**Approach:** Canonical control-room scheduler with workflow-first Automatic UI

---

## Overview

Phase 7 implements the control-room system’s first real automatic operations layer.

This phase is not about deciding which workflows deserve automation. That decision remains human-led and is supported by later analytics work. Phase 7 instead makes the documented automatic path actually function once a workflow has already been promoted from `manual` to `automatic`.

The phase adds four connected outcomes:

1. a canonical scheduler worker that fires due calendar rules
2. exact-time automatic publication for trusted workflows
3. end-of-day expiry for untouched manual drafts
4. a workflow-first `Automatic` tab with pause, resume, and move-to-manual controls

The scheduler must operate only on the canonical control-room model:

```text
CalendarRule -> TriggerEvent -> Workflow -> WorkflowVersion -> ContentJob -> DraftVariant
```

Legacy platform-specific queues such as `content_queue` and `linkedin_post` may continue to exist temporarily, but they are not the source of truth for Phase 7 automatic operations.

### Phase Objective

Build a reliable, one-shot scheduler system that:

- fires due calendar workflows
- creates canonical manual or automatic drafts
- publishes automatic drafts at exact times
- expires untouched manual drafts at local end-of-day
- exposes automatic workflow health and controls in the control-room UI
- supports canonical `x`, `linkedin`, and `instagram` workflows

---

## 1. Product Role

The control room is manual-first by default. Automatic mode exists for workflows that have already earned trust.

Phase 7 must preserve that product rule:

- new workflows still start in `manual`
- automatic mode remains explicit and reversible
- manual review remains the default control surface
- automatic mode becomes a runtime behavior layer, not a second content system

This means the scheduler is not a separate product. It is an operator tool that extends the same workflow model already visible in Manual, Calendar, Trigger Feed, and History.

---

## 2. Supported Automatic Operations

Phase 7 supports three scheduler duties.

### 2.1 Fire Due Calendar Rules

When a `CalendarRule` becomes due:

1. the worker claims the rule
2. a canonical `TriggerEvent(type=calendar)` is recorded
3. the workflow resolver loads the active `WorkflowVersion`
4. generation and compliance run through the canonical workflow path
5. one or more `DraftVariant` rows are created

### 2.2 Publish Due Automatic Drafts

When a canonical draft is due for automatic publication:

- it is published through the canonical platform adapter
- publication status is stored on the draft
- workflow health metadata is updated

### 2.3 Expire Stale Manual Drafts

When a manual draft reaches end-of-day in its workflow/account timezone:

- it leaves the active queue
- it moves to `Expired`
- it becomes read-only history

This is not optional cleanup. It is a locked product behavior from the control-room brief.

---

## 3. Worker Architecture

Phase 7 uses a **one-shot tick worker**.

### Why This Architecture

A one-shot worker is the best fit for the documented product and deployment shape:

- simpler than a long-running polling daemon
- easier to test deterministically
- safer in multi-instance environments
- a clean fit for Railway/cron execution every minute

### Entry Points

Phase 7 should create:

- `app/services/scheduler.py`
- one worker entrypoint script, such as:
  - `python -m app.services.scheduler`
  - or `scripts/run_scheduler_tick.py`

### Tick Contract

Each worker run executes one scheduler tick and exits.

Suggested public interface:

```python
class SchedulerService:
    def tick(self, now: datetime | None = None) -> SchedulerTickResult:
        ...
```

Suggested result shape:

- rules fired
- drafts created
- drafts published
- drafts expired
- workflow failures
- total duration

This result should be usable in logs, local smoke tests, and later platform health widgets.

---

## 4. Canonical State Model

Phase 7 must use workflow mode as the source of truth.

### 4.1 Manual Workflow Path

When a due calendar rule belongs to a `manual` workflow:

- create `TriggerEvent`
- create `ContentJob`
- create passing `DraftVariant(state=manual_ready)`
- set `expires_at` to end-of-day in the workflow timezone
- do not auto-publish

Manual drafts appear in:

- Manual queue
- Calendar all-day lane

### 4.2 Automatic Workflow Path

When a due calendar rule belongs to an `automatic` workflow:

- create `TriggerEvent`
- create `ContentJob`
- create passing `DraftVariant(state=automatic_ready)`
- set exact `scheduled_publish_at`
- publish later when due

Automatic drafts appear in:

- Automatic tab
- Calendar timed lane

### 4.3 Scheduled Manual Path

If a human schedules a manual draft:

- it remains canonical
- its state is `scheduled_manual`
- the scheduler publishes it at `scheduled_publish_at`
- it renders in the timed calendar lane even though its workflow is still manual

### 4.4 Publish Transitions

Canonical publish transitions are:

- `automatic_ready` -> `publishing` -> `published`
- `scheduled_manual` -> `publishing` -> `published`
- failed attempts move to `failed`

### 4.5 Expiry Transition

Canonical expiry transition is:

- `manual_ready` -> `expired`

Each expiry should record a canonical `ReviewAction(action=expire, actor="scheduler")`.

---

## 5. Scheduler Duties

Each tick runs the following duties in order.

## 5.1 Duty A: Fire Due Calendar Rules

The worker:

1. selects enabled, unpaused `CalendarRule` rows where `next_fire_at <= now`
2. claims them atomically
3. resolves the owning workflow
4. creates a calendar trigger event
5. runs the canonical generation path
6. sets the next `next_fire_at`

The worker must not fire the same rule twice in the same minute due to duplicate workers or retries.

### Required behavior

- rules for paused workflows are ignored
- disabled rules are ignored
- one rule failure does not abort the entire tick
- trigger provenance remains visible on resulting drafts

## 5.2 Duty B: Publish Due Automatic Drafts

The worker selects drafts where:

- `state in (automatic_ready, scheduled_manual)`
- `scheduled_publish_at <= now`

It then publishes through canonical platform adapters:

- X via `get_publisher("x")`
- LinkedIn via `get_publisher("linkedin")`
- Instagram via the existing asset-aware Instagram path

### Required behavior

- one failed publish must not block the rest of the tick
- drafts must be claimed before publish to avoid duplicate posting
- publish results must update draft state, ids, URLs, timestamps, and errors
- workflow-level health fields must be updated based on outcome

## 5.3 Duty C: Expire Manual Drafts

The worker selects `manual_ready` drafts where `expires_at <= now`.

It then:

- sets state to `expired`
- records an expire review action
- leaves the draft in read-only history

### Required behavior

- expiry uses the draft/workflow timezone, not server timezone
- already scheduled manual drafts do not expire through this path
- already published/rejected/failed drafts are ignored

---

## 6. Data Model Changes

Phase 7 should prefer targeted additive fields over a broad rewrite.

### 6.1 `workflows`

Add:

- `timezone`
- `paused_at`
- `last_run_at`
- `last_success_at`
- `last_error`
- `health_status`

Purpose:

- support operator controls
- support automatic-health UI
- support safe scheduler filtering

### 6.2 `calendar_rules`

Add:

- `publish_hour_local`
- `publish_minute_local`
- `all_day_generation`
- `last_fired_at`
- `claimed_at`
- `claimed_by`

Purpose:

- distinguish generation time from publish time
- support exact automatic publish scheduling
- support row claiming and auditability

### 6.3 `draft_variants`

Reuse existing:

- `scheduled_publish_at`
- `expires_at`

Add:

- `publish_attempted_at`
- `published_via`

Suggested `published_via` values:

- `automatic_workflow`
- `scheduled_manual`
- `post_now`

Purpose:

- clear provenance for how a post went live
- cleaner analytics and audit hooks later

### 6.4 Optional New Scheduler Log Table

Phase 7 may add a lightweight worker log table if needed for visibility, but it is not required if structured application logs are sufficient.

If added, it should store:

- tick started_at
- tick finished_at
- counts by duty
- error summaries

This is optional, not a scope anchor.

---

## 7. Automatic Tab Design

The Automatic tab should be **workflow-first**.

This matches the product: automatic mode is a trust level applied to workflows, not just a list of timed posts.

### 7.1 Workflow Card Contents

Each workflow row/card should show:

- workflow name
- platform
- mode
- timezone
- next trigger time
- configured publish time
- queued automatic draft count
- last success
- last failure
- health badge

### 7.2 Expanded Draft Detail

Each workflow card should support an expanded sub-list of scheduled drafts showing:

- content preview
- scheduled publish time
- trigger provenance
- current state
- platform-specific asset hint if relevant

### 7.3 Workflow Controls

Each automatic workflow should expose:

- `Pause`
- `Resume`
- `Move To Manual`

### 7.4 Control Semantics

#### Pause

Pause means:

- do not fire new calendar-trigger generations
- do not auto-publish future due drafts for that workflow
- preserve existing queued drafts and history

#### Resume

Resume means:

- workflow re-enters the scheduler
- normal due generation and auto-publish behavior continues

#### Move To Manual

Move To Manual means:

- workflow `mode` changes from `automatic` to `manual`
- future triggers create `manual_ready` drafts
- pending `automatic_ready` drafts for that workflow become `manual_ready`
- drafts already `publishing` are left alone

This control is the operational rollback for automatic mode.

---

## 8. Calendar And Home Integration

Phase 7 must make existing UI timing rules real, not just visual.

### 8.1 Calendar

The Calendar view must continue to show:

- manual items in the all-day lane
- automatic and scheduled items in exact time slots

The difference is that Phase 7 makes those times authoritative:

- manual items use end-of-day expiry
- automatic items use exact publish timestamps

### 8.2 Home

Home should keep the current summary counts and add automatic-health visibility.

Suggested additions:

- paused workflows
- unhealthy workflows
- upcoming automatic posts in next 24 hours

This should surface operational issues without making Home a full scheduler dashboard.

---

## 9. API Design

Phase 7 needs workflow-level automatic APIs in addition to the existing per-draft action routes.

### 9.1 Automatic Workflow Endpoints

Add:

- `GET /api/control-room/automatic/workflows`
- `POST /api/control-room/workflows/{workflow_id}/pause`
- `POST /api/control-room/workflows/{workflow_id}/resume`
- `POST /api/control-room/workflows/{workflow_id}/move-to-manual`

### 9.2 Scheduler Visibility Endpoint

Optional but recommended:

- `GET /api/control-room/scheduler/status`

This can expose:

- last tick time
- due rules count
- due draft count
- paused workflow count
- unhealthy workflow count

### 9.3 Existing APIs To Reuse

Keep using:

- existing manual draft actions
- existing draft detail route
- existing calendar and control-room shell routes

Phase 7 should extend those APIs, not replace them.

---

## 10. Cross-Platform Publication Model

Phase 7 must support canonical automatic operation for:

- `x`
- `linkedin`
- `instagram`

### 10.1 Source Of Truth

The source of truth is always the canonical draft row, not legacy platform-specific queue tables.

### 10.2 Platform Dispatch

The scheduler publishes through canonical adapters:

- X: generic publisher interface
- LinkedIn: LinkedIn publisher adapter already exposed through canonical publisher lookup
- Instagram: existing asset-aware publish path

### 10.3 No Platform-Specific Schedulers

Phase 7 must not introduce:

- separate scheduler loops per platform
- separate automatic queues per platform
- automatic publishing logic that bypasses canonical `DraftVariant`

This phase should move the runtime model toward convergence, not deeper fragmentation.

---

## 11. Reliability And Safety

### 11.1 Row Claiming

The scheduler must claim work safely so duplicate workers do not double-fire or double-publish.

This applies to:

- due calendar rules
- due automatic drafts
- expiry candidates if needed

### 11.2 Failure Isolation

One failed workflow or post must not stop the rest of the scheduler tick.

### 11.3 Observability

Every tick should emit structured logs containing:

- tick started/finished
- rules fired
- drafts published
- drafts expired
- failures by workflow/platform

### 11.4 Recovery

If a crash occurs during publish:

- drafts should not be left silently ambiguous
- status should remain inspectable in Automatic or Failed views
- the operator must be able to recover manually

Exact crash-recovery refinements can stay lightweight in Phase 7, but silent loss is not acceptable.

---

## 12. Phase Boundaries

Phase 7 includes:

- scheduler worker
- exact-time automatic publishing
- manual end-of-day expiry
- workflow-first Automatic tab
- pause/resume/move-to-manual controls
- cross-platform automatic support for canonical X, LinkedIn, and Instagram workflows

Phase 7 does **not** include:

- deciding which workflows deserve automatic mode
- analytics-based promotion confidence
- workflow studio / Claude improvement loop
- repurposing engine
- sports calendar ingestion
- partner API expansion beyond current canonical trigger shapes
- migration/removal of legacy platform-specific tables
- a long-running daemon scheduler
- deployment cron wiring beyond the documented worker entrypoint

---

## 13. Acceptance Criteria

Phase 7 is complete when all of the following are true:

1. `manual` workflows still create `manual_ready` drafts and those drafts expire at local end-of-day.
2. `automatic` workflows create `automatic_ready` drafts with exact `scheduled_publish_at` times.
3. due automatic drafts publish through canonical platform adapters.
4. due `scheduled_manual` drafts publish through the same scheduler worker.
5. paused workflows do not generate new content and do not auto-publish queued drafts.
6. `Move To Manual` stops future automatic execution and re-queues pending automatic drafts for manual handling.
7. the Automatic tab shows workflow health, next trigger time, publish time, and queued drafts.
8. the Calendar view shows manual items all-day and automatic items in timed slots.
9. all automatic behavior is driven by canonical control-room tables and routes, not legacy platform queues.

---

## 14. Implementation Direction

Phase 7 should be implemented as a hybrid scheduler:

- workflow-first control model
- draft-first publication execution

This keeps the Automatic UI aligned with operator mental models while keeping actual publish operations attached to canonical drafts where platform adapters already fit cleanly.

That is the right balance between the control-room brief, the current repo state, and the need to support X, LinkedIn, and Instagram without building a second architecture.
