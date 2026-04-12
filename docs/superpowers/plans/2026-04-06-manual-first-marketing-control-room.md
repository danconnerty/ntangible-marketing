# Manual-First Marketing Control Room Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current NTangible FastAPI content-generation backend into a full internal marketing control-room app with manual and automatic tabs, visible trigger provenance, workflow versioning, a searchable content brain, and a Claude-powered workflow improvement loop.

**Architecture:** Keep the current Python/FastAPI/Postgres codebase as the system of record. Add canonical workflow/trigger/review/memory tables, a server-rendered admin UI, and a separate scheduler worker. Reuse the current X generator/compliance/publisher code behind a new generic workflow engine, then expand to LinkedIn, Instagram, partner triggers, and analytics.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy, Alembic, Jinja2 templates, HTMX/Alpine or light JS, PostgreSQL, Anthropic SDK, pgvector, APScheduler (or equivalent DB-backed worker loop), pytest

---

## File Structure

### Existing Files To Reuse

- `app/agents/content_writer.py`
- `app/agents/compliance.py`
- `app/api/routes.py`
- `app/models/content.py`
- `app/models/linkedin.py`
- `app/publishers/*`

### New Backend Files

- `app/models/workflow.py`
- `app/models/trigger.py`
- `app/models/review.py`
- `app/models/memory.py`
- `app/models/analytics.py`
- `app/services/workflow_engine.py`
- `app/services/trigger_engine.py`
- `app/services/review_queue.py`
- `app/services/memory_retrieval.py`
- `app/services/workflow_editor.py`
- `app/services/scheduler.py`
- `app/services/analytics_ingest.py`
- `app/services/prompt_assembler.py`
- `app/api/control_room_routes.py`
- `app/api/workflow_routes.py`
- `app/api/trigger_routes.py`
- `app/api/history_routes.py`
- `app/api/analytics_routes.py`

### New UI Files

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

### Migrations

- `alembic/versions/<timestamp>_add_control_room_tables.py`
- `alembic/versions/<timestamp>_add_memory_tables.py`
- `alembic/versions/<timestamp>_add_scheduler_fields.py`

### Tests

- `tests/test_workflow_models.py`
- `tests/test_trigger_engine.py`
- `tests/test_review_queue.py`
- `tests/test_workflow_editor.py`
- `tests/test_memory_retrieval.py`
- `tests/test_control_room_api.py`
- `tests/test_web_manual_view.py`
- `tests/test_web_calendar_view.py`
- `tests/test_scheduler.py`

---

## Delivery Strategy

Build this in six deliverable slices instead of one giant refactor:

1. **Control-room foundation**
   Canonical schema, workflow objects, trigger events, review actions.
2. **Manual queue product**
   Manual tab, calendar all-day lane, reject/expire history, draft detail, post/schedule actions.
3. **Workflow intelligence**
   Brain/history, Claude workflow improvement, workflow versioning, previewing changed workflows.
4. **Automatic operations**
   Automatic tab, exact publish times, scheduler worker, end-of-day expiry jobs.
5. **Trigger expansion**
   External partner/news/calendar trigger ingestion and feed view.
6. **Analytics and handoff**
   Performance loops, workflow promotion confidence, monitoring, docs, launch checklist.

Each slice must leave the app in a demoable state.

---

### Task 1: Add Canonical Control-Room Schema

**Files:**
- Create: `app/models/workflow.py`
- Create: `app/models/trigger.py`
- Create: `app/models/review.py`
- Modify: `app/models/__init__.py`
- Create: `alembic/versions/<timestamp>_add_control_room_tables.py`
- Test: `tests/test_workflow_models.py`

- [ ] Define canonical enums: workflow mode, trigger type, trigger source, draft state, review action type.
- [ ] Add `Workflow` model with fields for name, slug, mode, platform, content type, active version id, fallback version id, enabled flag.
- [ ] Add `WorkflowVersion` model with immutable prompt/retrieval/routing config stored as JSONB plus version notes and author metadata.
- [ ] Add `CalendarRule` model for day/time recurrences and timezone.
- [ ] Add `TriggerEvent` model for calendar, external, and manual-request events.
- [ ] Add `ContentJob` model for one run of one workflow against one trigger.
- [ ] Add `DraftVariant` model for generated drafts, state, recommended time, asset refs, platform payload, and compliance snapshots.
- [ ] Add `ReviewAction` model for post, schedule, reject, and expire actions.
- [ ] Write tests covering enum values, default states, and key relationships.
- [ ] Run `pytest tests/test_workflow_models.py -q`.
- [ ] Run `alembic upgrade head`.

**Notes:**
- Do not remove `content_queue` or `linkedin_post` in this task.
- Treat the new models as the canonical future control-room layer.

---

### Task 2: Build Workflow And Trigger Services

**Files:**
- Create: `app/services/workflow_engine.py`
- Create: `app/services/trigger_engine.py`
- Create: `app/services/prompt_assembler.py`
- Test: `tests/test_trigger_engine.py`

- [ ] Create a workflow resolver that maps a trigger event to a workflow and active version.
- [ ] Create a prompt-assembly service that pulls brand rules, platform config, workflow version config, and retrieved memory into one structured generation payload.
- [ ] Add trigger normalization so all sources become the same internal object shape.
- [ ] Support three trigger families: `calendar`, `external`, `manual_request`.
- [ ] Add routing rules that decide whether the output belongs in manual or automatic handling based on workflow mode.
- [ ] Build representative fixtures for a Tuesday calendar trigger, a partner commitment event, and a manual Claude request.
- [ ] Verify that the resolver returns deterministic workflow/version selections.
- [ ] Run `pytest tests/test_trigger_engine.py -q`.

**Notes:**
- This is the seam where the current X generation code gets wrapped instead of called directly from routes.

---

### Task 3: Introduce A Generic Review Queue API

**Files:**
- Create: `app/services/review_queue.py`
- Create: `app/api/control_room_routes.py`
- Create: `app/api/history_routes.py`
- Modify: `app/main.py`
- Test: `tests/test_review_queue.py`
- Test: `tests/test_control_room_api.py`

- [ ] Add endpoints for listing manual queue items, automatic queue items, rejected history, and expired history.
- [ ] Add draft detail endpoint showing trigger reason, workflow, workflow version, content, asset references, and compliance results.
- [ ] Add actions: `post_now`, `schedule`, `reject`.
- [ ] Add read-only history endpoints for `rejected` and `expired`.
- [ ] Enforce end-of-day expiry semantics for manual items.
- [ ] Preserve distinct meanings for `rejected` vs `expired`.
- [ ] Add API contracts for “why this draft exists.”
- [ ] Back the endpoints with the new canonical models, not the old platform-specific tables.
- [ ] Run `pytest tests/test_review_queue.py tests/test_control_room_api.py -q`.

**Notes:**
- This is the first point where the boss can conceptually operate the system.
- UI comes next, but the queue behavior must exist in the backend first.

---

### Task 4: Build The Admin UI Shell

**Files:**
- Create: `app/web/routes.py`
- Create: `app/web/templates/base.html`
- Create: `app/web/templates/home.html`
- Create: `app/static/css/control_room.css`
- Create: `app/static/js/control_room.js`
- Modify: `app/main.py`
- Test: `tests/test_web_manual_view.py`

- [ ] Mount a web router for authenticated internal pages.
- [ ] Create the global shell with sidebar, top bar, Claude entry box, and status badges.
- [ ] Add Home page cards for manual count, automatic count, new triggers, failures, and workflow changes.
- [ ] Implement a consistent card pattern for drafts, workflow summaries, and trigger events.
- [ ] Add a right-hand detail drawer pattern that can be reused by manual, automatic, rejected, and trigger views.
- [ ] Add CSS tokens for statuses, platform badges, timing badges, and queue-state colors.
- [ ] Keep the UI intentionally internal-tool simple: clean, fast, readable, not marketing-site styled.
- [ ] Run route smoke tests for the web shell.

**Notes:**
- Use server-rendered HTML and light interaction helpers. Do not block on introducing a separate frontend app.

---

### Task 5: Implement The Manual Tab, Calendar, Rejected, And Expired Views

**Files:**
- Create: `app/web/templates/manual.html`
- Create: `app/web/templates/calendar.html`
- Create: `app/web/templates/rejected.html`
- Create: `app/web/templates/expired.html`
- Modify: `app/web/routes.py`
- Test: `tests/test_web_manual_view.py`
- Test: `tests/test_web_calendar_view.py`

- [ ] Render manual items in an all-day queue view with visible trigger provenance.
- [ ] Show per-card actions: `Post Now`, `Schedule`, `Reject`, `Why This Draft?`, `Improve Workflow`.
- [ ] Build the calendar view with two behaviors:
  - manual items in all-day lane
  - automatic items in timed slots
- [ ] Build rejected view as read-only history with rejection notes and workflow/version context.
- [ ] Build expired view as read-only history with expiry timestamps.
- [ ] Add detail drawer templates for draft content, asset preview, compliance output, and trigger origin.
- [ ] Add a “recommended time” badge on manual items without forcing publish time.
- [ ] Run UI view tests and route smoke tests.

**Notes:**
- At the end of this task, the manual-first operator experience should be demoable.

---

### Task 6: Add The Brain / History Retrieval Layer

**Files:**
- Create: `app/models/memory.py`
- Create: `app/services/memory_retrieval.py`
- Create: `app/api/history_routes.py`
- Create: `app/web/templates/brain.html`
- Create: `alembic/versions/<timestamp>_add_memory_tables.py`
- Test: `tests/test_memory_retrieval.py`

- [ ] Define `MemoryItem` and `MemoryEmbedding` models.
- [ ] Ingest current approved, rejected, expired, and published content into canonical memory records.
- [ ] Add metadata fields for platform, workflow, workflow version, trigger type, status, tags, partner, and metrics.
- [ ] Add search filters for platform, status, workflow, trigger type, intent, and date range.
- [ ] Add semantic search support via pgvector for “similar past posts.”
- [ ] Add ranked retrieval APIs for:
  - similar approved posts
  - similar rejected posts
  - best-performing posts by platform/workflow
  - recent examples for a workflow
- [ ] Render a Brain/History page with searchable filters and result cards.
- [ ] Run `pytest tests/test_memory_retrieval.py -q`.

**Notes:**
- This task turns the “brain” into a real system instead of vague prompt context.

---

### Task 7: Build Workflow Studio And Claude-Powered Workflow Improvement

**Files:**
- Create: `app/services/workflow_editor.py`
- Create: `app/api/workflow_routes.py`
- Create: `app/web/templates/workflow_detail.html`
- Test: `tests/test_workflow_editor.py`

- [ ] Add a workflow detail page showing:
  - current mode
  - trigger config
  - current version summary
  - version history
  - recent approval/rejection trends
  - representative approved examples
  - representative rejected examples
- [ ] Add “Why This Draft?” endpoint that explains which workflow, version, trigger, and retrieved examples produced a draft.
- [ ] Add “Improve Workflow” action that sends structured context to Claude.
- [ ] Require Claude to return a structured workflow patch, not free text.
- [ ] Store proposed workflow changes as a new inactive `WorkflowVersion`.
- [ ] Add preview generation against representative triggers before activation.
- [ ] Add explicit activation endpoint to switch the live version.
- [ ] Log what changed and why.
- [ ] Run `pytest tests/test_workflow_editor.py -q`.

**Notes:**
- This task is the core of the “don’t edit one post; fix the process” product behavior.

---

### Task 8: Add Scheduler Worker And Automatic Tab

**Files:**
- Create: `app/services/scheduler.py`
- Create: `app/web/templates/automatic.html`
- Create: `alembic/versions/<timestamp>_add_scheduler_fields.py`
- Test: `tests/test_scheduler.py`

- [ ] Add a separate worker entrypoint that claims due jobs from Postgres.
- [ ] Support three worker duties:
  - fire due calendar rules
  - expire untouched manual drafts at day end
  - publish automatic drafts at exact configured times
- [ ] Add publish-time fields and state transitions needed for automatic items.
- [ ] Build the Automatic tab with workflow rows/cards showing next run, publish time, status, and quick controls.
- [ ] Add actions to pause, resume, and move a workflow back to manual.
- [ ] Add platform health checks and failure alerts surfaced in Home/Automatic views.
- [ ] Run scheduler tests and a full smoke path with mock publishers.

**Notes:**
- Automatic should be built only after manual behavior is stable and inspectable.

---

### Task 9: Add External Trigger Ingestion And Trigger Feed

**Files:**
- Create: `app/api/trigger_routes.py`
- Create: `app/web/templates/trigger_feed.html`
- Create: `app/models/partner_source.py` or fold into `app/models/trigger.py`
- Test: `tests/test_trigger_engine.py`
- Test: `tests/test_control_room_api.py`

- [ ] Add APIs for external trigger ingestion from partner webhooks, file imports, or manual event entry.
- [ ] Normalize incoming trigger payloads into `TriggerEvent`.
- [ ] Build the Trigger Feed page showing source, event type, partner, created time, and resulting draft/job status.
- [ ] Add placeholder integrations for sports calendar and partner event types even if data entry starts manually.
- [ ] Wire external triggers into manual queue generation for manual-mode workflows.
- [ ] Add clear audit logging so every generated post can point back to its external event.

**Notes:**
- Even if partner APIs are not live yet, the ingestion shape should be finalized now.

---

### Task 10: Add Analytics Ingestion And Workflow Confidence

**Files:**
- Create: `app/models/analytics.py`
- Create: `app/services/analytics_ingest.py`
- Create: `app/api/analytics_routes.py`
- Create: `app/web/templates/analytics.html`
- Test: `tests/test_control_room_api.py`

- [ ] Add analytics snapshot tables for published content.
- [ ] Ingest engagement metrics back into the brain for approved content.
- [ ] Calculate workflow-level health metrics:
  - approval rate
  - rejection rate
  - expiration rate
  - publication success rate
  - engagement percentile by workflow
- [ ] Surface “promotion confidence” to help decide when a manual workflow can move to automatic.
- [ ] Render analytics UI grouped by workflow, platform, and trigger type.
- [ ] Add filters for date range and platform.

**Notes:**
- This is what makes automatic promotion evidence-based instead of guesswork.

---

### Task 11: Platform Expansion And Transition Layer Cleanup

**Files:**
- Modify: `app/agents/*`
- Modify: `app/publishers/*`
- Modify: `app/api/routes.py`
- Modify: `app/models/content.py`
- Modify: `app/models/linkedin.py`
- Add: Instagram equivalents where needed

- [ ] Wrap existing X generation/compliance logic in the new workflow engine instead of letting old routes stay the only source of truth.
- [ ] Merge the planned LinkedIn work into the canonical control-room flow.
- [ ] Add Instagram adapter interfaces and placeholder mock publisher first.
- [ ] Introduce a unified publication abstraction so Manual and Automatic tabs are cross-platform views, not X-only.
- [ ] Decide when to retire, adapt, or proxy old X-only routes to the new queue engine.

**Notes:**
- Do not let the old X-only API and the new control room diverge permanently.

---

### Task 12: Hardening, Launch Checklist, And Handoff

**Files:**
- Create: `docs/control-room-operator-guide.md`
- Create: `docs/control-room-admin-guide.md`
- Create: `docs/control-room-runbook.md`
- Modify: `.env.example`

- [ ] Add operator guide for daily use.
- [ ] Add admin guide for workflow creation, mode switching, and workflow improvements.
- [ ] Add runbook for scheduler issues, failed publications, and platform outages.
- [ ] Add seed data or fixtures so the app can be demoed immediately.
- [ ] Add backup/export procedure for workflows, memory items, and analytics.
- [ ] Verify staging flow with mock publishers.
- [ ] Verify production readiness with real platform credentials in a controlled environment.
- [ ] Run a full end-to-end walkthrough:
  - manual calendar trigger
  - manual external trigger
  - rejection
  - workflow improvement
  - next generated draft
  - automatic publish

---

## Verification Checklist

- [ ] Boss can log into one app and understand the day’s work without opening raw APIs.
- [ ] Every draft shows why it was generated.
- [ ] Manual drafts can be posted, scheduled, rejected, or allowed to expire.
- [ ] Rejected and expired views are read-only and distinct.
- [ ] Claude can improve workflows by creating new workflow versions.
- [ ] Calendar shows manual items as all-day and automatic items at exact times.
- [ ] Trigger Feed shows external events and their resulting drafts.
- [ ] Brain search can find approved, rejected, and high-performing past posts.
- [ ] Automatic workflows publish through the scheduler at exact times.
- [ ] Workflow metrics help decide when to promote from manual to automatic.

---

## Recommended Delivery Order

If this is going to your boss as a believable “we can build this” plan, the order should be:

1. Task 1–3: backend control-room foundation
2. Task 4–5: manual-first operator UI
3. Task 6–7: brain + workflow improvement loop
4. Task 8: automatic scheduler and tab
5. Task 9–10: external triggers + analytics
6. Task 11–12: platform cleanup, hardening, handoff

That gives you a usable manual-first app early, instead of making the boss wait for the full automation stack before anything is visible.
