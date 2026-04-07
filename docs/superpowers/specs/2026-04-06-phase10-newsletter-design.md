# Phase 10: Newsletter System + ESP Integration — Design Spec

**Date:** 2026-04-06  
**Status:** Draft for review  
**Approach:** Canonical control-room newsletter lane with segment-aware ESP delivery

---

## Overview

Phase 10 implements the numbered roadmap's newsletter slice:

1. monthly newsletter draft generation
2. audience-segment-aware content assembly
3. manual review before send
4. ESP-backed delivery and basic deliverability tracking

This phase should not become a parallel email subsystem. The repo already has a canonical control-room architecture built around workflows, triggers, canonical drafts, review actions, publication records, analytics, and memory. Newsletter support should attach to that architecture directly.

The operator experience should remain consistent with the rest of the product:

- a monthly trigger fires
- the workflow engine resolves the active workflow version
- the system generates one draft per target segment
- drafts land in `Manual` by default
- the operator reviews, rejects, schedules, or sends them
- send history, rejection history, and future workflow improvement stay visible in the same control room

### Phase Objective

Build a production-ready newsletter lane that:

- introduces `newsletter` as a first-class control-room platform
- generates monthly newsletter drafts by audience segment
- routes newsletter drafts through the canonical review queue
- delivers approved drafts through a reputable ESP
- preserves provenance, history, analytics hooks, and workflow improvement evidence

---

## 1. Product Role

The newsletter is NTangible's first true owned-media channel in the roadmap.

Unlike X, LinkedIn, or Instagram, the newsletter is not optimized for feed velocity. Its job is to deliver high-signal, role-specific value directly to opted-in audiences. The blueprint is explicit:

- cadence is monthly, not weekly
- quality matters more than frequency
- each edition must teach something or prove something
- deliverability and spam compliance are non-negotiable

Phase 10 should therefore treat newsletter as:

- **owned media**
- **manual-first**
- **segment-specific**
- **workflow-driven**

The operator should not manage newsletters in a separate marketing tool mindset. Newsletter work should feel like another workflow lane in the same control room.

---

## 2. Core Product Rules

Phase 10 must preserve the following rules from the blueprint and implementation brief.

### 2.1 Manual Review Is Required By Default

The blueprint says the engine generates the draft and Dan reviews before send.

That means:

- newsletter workflows default to `manual`
- generated newsletter drafts enter `Manual`
- sending without human review is out of scope for the initial rollout

### 2.2 Monthly Cadence

Phase 10 is a monthly newsletter system, not a weekly blast engine.

Calendar rules may support more flexible schedules later, but the documented product target for this phase is:

- one monthly edition cadence
- skip weak months rather than send filler

### 2.3 Audience Segmentation Is Required

At minimum, Phase 10 supports two audience segments:

1. `coaches_front_offices`
2. `partners_event_directors`

Additional segments such as `parents_athletes` are deferred.

### 2.4 Structured Value Content

Each newsletter edition must contain:

- one data insight or trend
- one client or partner proof point
- one product or feature update
- one CTA

No fluff. The generation path and compliance layer should enforce this structure.

### 2.5 Deliverability Guardrails Are Mandatory

Phase 10 must send through a reputable ESP and assume:

- double opt-in is handled by the ESP/list setup
- unsubscribe support is mandatory
- sender-domain hygiene matters
- open-rate monitoring is important, but does not yet require a hidden automation policy engine

---

## 3. Canonical Architecture Fit

Newsletter support should extend the existing control-room model rather than bypass it.

Canonical path:

```text
CalendarRule -> TriggerEvent -> Workflow -> WorkflowVersion -> ContentJob -> DraftVariant
-> ReviewAction -> PublicationRecord -> AnalyticsSnapshot -> Memory
```

Phase 10 must reuse this exact path.

### 3.1 First-Class Platform

Add `newsletter` to the canonical `Platform` enum.

This is the key architectural choice. Newsletter is not only a content type. It has:

- distinct generation behavior
- distinct compliance behavior
- distinct publication behavior
- distinct analytics metadata

Treating it as a platform keeps the workflow engine, review queue, publication records, and analytics model coherent.

### 3.2 No Parallel Queue Model

Do not create newsletter-only queue tables or review history tables.

Newsletter drafts should remain canonical `DraftVariant` rows with newsletter-specific metadata stored in payload fields, not in a disconnected subsystem.

### 3.3 Trigger Model Stays The Same

No new trigger type is required for Phase 10.

Newsletter workflows should initially be driven by:

- `calendar` for monthly editions
- optionally `manual_request` for ad hoc test editions or operator-requested drafts

### 3.4 Review Model Stays The Same

Newsletter drafts should use the existing review actions:

- `post_now` = send immediately through the ESP
- `schedule` = queue a future send time
- `reject` = move to canonical rejected history

This keeps newsletter behavior aligned with the control-room product model.

---

## 4. Audience Segment Model

Phase 10 needs segment-aware workflows and draft generation, but should avoid schema sprawl.

### 4.1 Required Segments

The first rollout supports:

- `coaches_front_offices`
- `partners_event_directors`

These segments have different editorial goals:

- **Coaches / scouts / front offices**
  Focus on data insights, recruiting intelligence, and platform updates.

- **Partners / event directors**
  Focus on integration ROI, assessment volume, operational proof, and feature releases.

### 4.2 Segment Placement

Segment targeting should live in workflow version config, not in a new top-level workflow column family.

Recommended direction:

- `routing.target_audience_segment`
- `prompt.system_prompt_additions`
- `cta.cta_preferences`
- `formatting.require_subject_line`
- `formatting.max_sections`

### 4.3 Draft Cardinality

When a newsletter workflow fires, the system should create one draft per configured audience segment.

For the default monthly workflow this means:

- one `DraftVariant` for `coaches_front_offices`
- one `DraftVariant` for `partners_event_directors`

Each draft should be independently reviewable, rejectable, schedulable, and sendable.

---

## 5. Generation Architecture

Newsletter generation should plug into the existing workflow engine through one new platform path.

### 5.1 New Components

Phase 10 should introduce:

- `app/agents/newsletter_writer.py`
- `app/agents/newsletter_compliance.py`
- `app/publishers/newsletter_base.py`
- `app/publishers/newsletter_mock.py`
- one real ESP adapter such as:
  - `app/publishers/mailchimp_http.py`
  - or `app/publishers/convertkit_http.py`

### 5.2 Existing Components To Extend

Phase 10 should extend:

- `app/models/workflow.py`
- `app/services/platform_generation.py`
- `app/publishers/__init__.py`
- `app/services/review_queue.py`
- `app/services/analytics_ingest.py`
- `app/services/memory_retrieval.py`
- control-room APIs and templates that render platform labels or draft actions

### 5.3 Prompt Assembly

Newsletter generation should continue using `PromptAssembler`.

The assembler already supports:

- workflow metadata
- trigger context
- approved and rejected examples
- CTA preferences
- workflow-version config

Phase 10 should build on that seam, not replace it. Newsletter generation needs the same retrieval-backed context as the social lanes, but should output a richer structured payload.

### 5.4 Generated Newsletter Payload

The newsletter writer should return a structured result containing at minimum:

- `subject`
- `preview_text`
- `segment`
- `hook`
- `proof_point`
- `product_update`
- `cta`
- `body_markdown`
- `body_html` or renderable section structure

`DraftVariant.content` should contain the human-readable newsletter body. Structured fields should be preserved in `compliance_result` or another existing JSON payload field so the UI and publisher can access subject and preview text without reparsing raw prose.

---

## 6. Compliance And Deliverability Rules

Newsletter compliance is materially different from social compliance.

Phase 10 should add a newsletter-specific compliance layer that validates both editorial structure and send readiness.

### 6.1 Required Content Checks

The compliance layer should fail drafts that do not contain:

- a subject line
- preview text
- a declared audience segment
- one data insight or trend
- one proof point
- one product or feature update
- one CTA

### 6.2 Quality And Spam-Risk Checks

The compliance layer should also reject or flag drafts for:

- all-caps or shouty subject lines
- misleading urgency language
- excessive exclamation marks
- missing plain educational or proof value
- body length outside a reasonable monthly-edition range

### 6.3 Send Readiness Checks

The send path must not proceed if:

- no ESP adapter is configured
- required ESP credentials are missing
- target list or segment mapping is missing
- unsubscribe support is not available in the configured adapter

These failures should be explicit operator-visible errors, not silent no-ops.

### 6.4 Deliverability Scope

Phase 10 should assume operational best practices such as SPF, DKIM, DMARC, and double opt-in are managed outside application logic, but it should preserve metadata that allows the operator to monitor results later.

Do not build a full deliverability platform in this phase.

---

## 7. Publisher And ESP Contract

Phase 10 needs one generic newsletter-sending contract so the workflow engine remains ESP-agnostic.

### 7.1 Generic Publisher Contract

The newsletter publisher base should accept:

- subject
- preview text
- body content
- target segment or list identifier
- optional scheduled send time

The result should normalize:

- send success/failure
- campaign or send id
- hosted archive URL when available
- send timestamp
- provider error details

### 7.2 First Real Adapter

Phase 10 should ship with:

- a mock adapter for tests and local development
- one real adapter for a reputable ESP such as Mailchimp or ConvertKit

The exact provider can be chosen during implementation, but provider choice should remain a config concern rather than a workflow rewrite.

### 7.3 Publication Record Mapping

Newsletter sends should record canonical publication metadata:

- `PublicationRecord.platform = newsletter`
- `platform_post_id` = ESP campaign id or send id
- `post_url` = hosted archive/campaign URL when available
- `published_at` = actual send time

This keeps the analytics and memory layers consistent with the rest of the control room.

---

## 8. Canonical Data Shape

Phase 10 should prefer additive enum and payload changes over a newsletter-only schema fork.

### 8.1 Workflow

Newsletter workflows should use:

- `platform = newsletter`
- `content_type = monthly_newsletter` or a related owned-media label
- `mode = manual` by default

### 8.2 Workflow Version Config

The existing JSONB workflow version config remains the source of truth.

Newsletter-specific meaning should be expressed through existing sections:

- `prompt`
- `retrieval`
- `formatting`
- `routing`
- `timing`
- `cta`

Suggested newsletter-specific config fields:

```json
{
  "routing": {
    "target_content_type": "monthly_newsletter",
    "target_intent": "owned_media",
    "target_audience_segment": "coaches_front_offices"
  },
  "formatting": {
    "require_subject_line": true,
    "max_sections": 4
  },
  "cta": {
    "cta_preferences": ["book_demo", "reply", "learn_more"]
  }
}
```

The config model may need small schema extensions for newsletter-specific validation, but Phase 10 should not scatter these settings into many SQL columns.

### 8.3 Draft Variant

Newsletter drafts should store:

- newsletter body in `DraftVariant.content`
- send timing in existing scheduling fields
- subject/preview/segment/section metadata in `compliance_result`
- provider-specific failure reasons in `failure_reason`

This is sufficient for review, publish, analytics, and history without a new newsletter draft table.

---

## 9. Operator Workflow

Phase 10 must feel like part of the control room, not an external campaign manager.

### 9.1 Monthly Generation Flow

1. A monthly newsletter `CalendarRule` becomes due.
2. A canonical `TriggerEvent(type=calendar)` is recorded.
3. The workflow engine resolves the active newsletter workflow version.
4. Prompt assembly retrieves relevant approved and rejected examples.
5. Newsletter generation produces one draft per configured audience segment.
6. Newsletter compliance validates structure and send readiness.
7. Passing drafts enter `Manual`.

### 9.2 Manual Review Flow

Each newsletter draft card should show enough metadata to make email review practical:

- workflow name
- target audience segment
- subject line
- preview text
- content preview
- trigger provenance
- recommended or scheduled send time
- compliance state

Actions remain:

- `Post Now`
- `Schedule`
- `Reject`
- `Why This Draft?`
- `Improve Workflow`

### 9.3 Schedule And Send

`Post Now` should send immediately through the configured newsletter publisher.

`Schedule` should reuse the canonical scheduled-manual path:

- move draft to `scheduled_manual`
- set `scheduled_publish_at`
- let the existing scheduler publish it at the due time

This keeps newsletter sending consistent with other timed publication paths.

### 9.4 Rejection And Improvement

Rejected newsletter drafts should move to canonical rejected history with notes.

Those notes, along with workflow/version metadata and future analytics, should later become evidence for workflow improvement. The system should optimize future editions, not only encourage one-off editing.

---

## 10. UI Expectations

Phase 10 should reuse the current control-room UI instead of creating a newsletter-specific surface.

### 10.1 Manual Queue

Manual queue cards and detail drawers should render newsletter-specific metadata cleanly:

- segment badge
- subject line
- preview text
- send/archive metadata after publish

### 10.2 Calendar

Manual newsletter drafts should appear in the all-day lane until scheduled.

Scheduled newsletter drafts should appear in timed slots using the same rules as scheduled manual social drafts.

### 10.3 History

Rejected and expired newsletter drafts should be visible in existing read-only history views.

### 10.4 Workflow Detail

Workflow detail should make newsletter segment intent visible and should preserve newsletter drafts as part of future “Improve Workflow” evidence.

No dedicated newsletter dashboard is required in Phase 10.

---

## 11. Analytics And Memory Fit

Newsletter should close the same feedback loop as the rest of the control room.

### 11.1 Publication Analytics

Phase 10 should record send metadata through the canonical publication path and persist lightweight metrics when the ESP exposes them, such as:

- delivered count
- open rate
- click rate
- unsubscribe count

This phase does not need a bespoke newsletter analytics dashboard. It only needs to preserve the data in a way the existing analytics layer can build on.

### 11.2 Open-Rate Guardrail

The blueprint says to pause and audit if open rates drop below 25%.

Phase 10 should treat that as an operator-visible metric and future workflow signal, not as a hidden auto-disable behavior. The analytics layer should make it possible to see and act on the risk, but not silently suspend sends yet.

### 11.3 Memory

Newsletter drafts and sends should become first-class memory items so future retrieval can use:

- approved newsletter examples
- rejected newsletter examples
- newsletter workflow outcomes
- cross-channel owned-media patterns

This matters because the workflow engine should learn from successful and weak editions over time.

---

## 12. Phase Boundaries

Phase 10 includes:

- `newsletter` as a canonical platform
- monthly workflow support through existing calendar triggers
- two required audience segments
- newsletter writer and newsletter compliance
- manual review plus scheduled or immediate send
- mock plus one real ESP adapter
- publication record and analytics hooks for newsletter sends

Phase 10 does **not** include:

- autonomous recurring sends without review
- complex drip or nurture campaign builders
- parent/athlete segmentation rollout
- rich visual email-template editing
- newsletter-only queue/history architecture
- a separate campaign management product

---

## 13. Completion Criteria

Phase 10 is complete when all of the following are true:

1. The canonical platform model supports `newsletter`.
2. A monthly newsletter workflow can generate one draft per required audience segment.
3. Newsletter drafts enter the canonical manual queue and show the right review metadata.
4. Operators can reject, schedule, or send newsletter drafts through the same review model used elsewhere.
5. A configured ESP adapter can send approved newsletter drafts and store canonical publication records.
6. Newsletter sends contribute to analytics and memory hooks without creating a parallel subsystem.
7. The implementation fits the current control-room architecture and does not revive platform-specific queue drift.
