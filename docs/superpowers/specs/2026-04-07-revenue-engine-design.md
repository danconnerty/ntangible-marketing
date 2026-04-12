# Revenue Engine Design

**Date:** 2026-04-07  
**Status:** Approved at design level, pending written-spec review  
**Scope:** sales content engine, partner sales enablement, revenue intent tagging, and conversion tracking

---

## Goal

Add the missing revenue side of the NTangible blueprint so the control room can generate, review, track, and improve content whose primary job is to drive:

- demos
- registrations
- partner activation
- follow-up outreach
- landing-page and email conversion

This is not a separate CRM. It is a canonical revenue layer inside the existing control-room architecture.

---

## Product Outcome

The revenue engine extends the current control room with five outcomes:

1. **Revenue intent becomes first-class**
   Every revenue-oriented draft, workflow, campaign run, lead nurture task, and partner sales package can be identified, searched, filtered, and analyzed as `intent = revenue`.

2. **Repeatable sales motions become configurable**
   Operators can run canonical revenue playbooks such as:
   - demo push
   - registration push
   - partner ROI summary
   - coach or operator outreach
   - landing page copy
   - follow-up email sequence

3. **Partner sales enablement becomes real**
   Alliance and FSS events can produce partner-facing sales collateral, not just social content.

4. **Revenue generation reuses the same workflow stack**
   Revenue content still runs through:
   - triggers
   - workflows
   - workflow versions
   - memory retrieval
   - compliance
   - manual-first review
   - analytics

5. **Conversions become observable**
   Revenue workflows declare their target outcome and the system can record downstream conversion evidence against that goal.

---

## In Scope

### Revenue Motions

- `demo_push`
- `registration_push`
- `partner_roi_summary`
- `coach_outreach`
- `email_followup`
- `landing_page_copy`
- `sales_one_pager`

### Content Outputs

- revenue-oriented social drafts
- partner registration push packages
- partner ROI summary packages
- email copy
- landing page copy blocks
- one-pager copy payloads

### Surfaces

- control-room `Revenue` screen
- revenue API routes
- canonical trigger/workflow execution
- partner sales package generation
- conversion-goal and conversion-event storage

### Reused Inputs

- campaign runs
- lead nurture tasks
- partner events
- manual operator requests

---

## Out Of Scope

- full CRM or deal pipeline replacement
- billing, invoices, contracts, or attribution modeling
- automatic outbound email sending beyond existing publisher paths
- ad-buying systems
- multi-touch attribution math
- sales team staffing or task assignment workflow

These can be added later without changing the core revenue architecture.

---

## Architecture

The revenue engine stays inside the modular monolith and uses the same canonical content pipeline:

```text
campaign / lead / partner / manual request
-> revenue playbook resolver
-> trigger engine
-> workflow engine
-> prompt assembler with revenue context
-> draft variants with intent = revenue
-> manual review / schedule / publish
-> conversion evidence ingest
-> analytics + memory write-back
```

### New canonical records

- `RevenuePlaybook`
- `RevenueExecution`
- `ConversionGoal`
- `ConversionEvent`
- `SalesEnablementPackage`

### Existing systems reused

- `TriggerEvent`
- `Workflow` / `WorkflowVersion`
- `ContentJob`
- `DraftVariant`
- `Campaign`
- `LeadAccount`
- `LeadNurtureTask`
- `PartnerEventRecord`
- `PartnerDeliveryBundle`
- scheduler
- analytics
- memory retrieval
- review queue

---

## Design Principles

### Revenue Is A Workflow Concern, Not A Side Flag

Revenue content should not be scattered as ad hoc `if sales then ...` branches in campaign and lead services.

Instead:

- revenue motions resolve to explicit playbooks
- playbooks point to workflows
- workflows produce drafts with canonical revenue context

### Intent Must Travel End To End

If a draft is revenue-oriented, the system must preserve that fact in:

- trigger payloads
- prompt snapshots
- draft variants
- publication records
- analytics summaries
- memory items

### Partner Sales Enablement Is Not The Same As Social Packaging

Partner social bundles and partner sales packages are related but not identical.

Social packages are built for posting.
Sales enablement packages are built for registration pushes, ROI summaries, and other partner-facing revenue motions.

They should share provenance, but not be forced into the exact same data shape.

### Manual-First Still Applies

Revenue content is more sensitive than brand content.

All new revenue workflows start in `manual` mode.
Automatic mode is allowed later, but only after real operator confidence.

---

## Data Model

### RevenuePlaybook

Stores a repeatable revenue motion.

Required fields:

- slug
- name
- description
- playbook type
- target workflow id
- target platform or output type
- persona
- offer
- CTA
- default audience
- default proof points
- active flag
- metadata/config JSON

Examples:

- `alliance-registration-push`
- `fss-roi-summary`
- `coach-demo-push-linkedin`
- `landing-page-copy-spring-campaign`

### RevenueExecution

Stores one run of a revenue playbook.

Required fields:

- revenue playbook id
- source kind: `campaign`, `lead`, `partner_event`, `manual`
- source id
- trigger event id
- content job id
- actor
- execution status
- summary JSON

This provides a stable audit trail for revenue runs without overloading campaigns or lead tasks.

### ConversionGoal

Stores what a workflow or playbook is trying to cause.

Required fields:

- slug
- name
- metric type
- workflow id or revenue playbook id
- target count or target rate
- attribution window days
- active flag
- metadata JSON

Examples:

- `alliance-registration-completions`
- `demo-bookings-linkedin`
- `roi-summary-partner-followup`

### ConversionEvent

Stores observed downstream outcomes.

Required fields:

- conversion goal id
- external event id
- source kind
- source reference
- partner slug or lead id where relevant
- captured at
- metric value
- metadata JSON

This is append-only evidence used for analytics.

### SalesEnablementPackage

Stores partner-facing revenue packages.

Required fields:

- partner account id
- partner event record id, nullable for non-partner packages
- revenue playbook id
- draft variant id, nullable when the package is document-only
- package kind
- status
- headline
- body copy
- CTA
- asset ids
- payload JSON
- usage notes
- delivered at

Package kinds:

- `registration_push`
- `roi_summary`
- `one_pager`
- `email_copy`

---

## Revenue Context Model

Revenue generation needs richer context than brand-only workflows.

The canonical `revenue_context` payload should support:

- playbook slug and type
- persona
- audience
- offer
- CTA
- proof points
- conversion goal
- campaign context
- lead context
- partner context

This context should be added to:

- `TriggerEvent.source_payload`
- `ContentJob.prompt_snapshot`
- workflow improvement context
- analytics grouping

---

## Routing Rules

### Shared Rules

- all revenue-generated drafts must persist `intent = revenue`
- revenue drafts may still carry `campaign`, `partner`, or `lead` context at the same time
- all revenue playbooks must route through canonical workflows, not bespoke one-off publishers
- all revenue playbooks default to manual review

### Source-To-Playbook Mapping

- `Campaign`
  - can trigger revenue playbooks for social conversion pushes, landing page copy, and email copy

- `Lead`
  - can trigger revenue playbooks for coach outreach, follow-up emails, and proof-led social follow-up

- `PartnerEventRecord`
  - can trigger revenue playbooks for registration pushes and ROI summaries

- `Manual`
  - operators can run ad hoc revenue playbooks directly from the control room

### Output Routing

- `demo_push`
  - LinkedIn post
  - X post
  - follow-up email draft when configured

- `registration_push`
  - LinkedIn post
  - X post
  - Instagram support post when partner-facing
  - partner sales package

- `partner_roi_summary`
  - partner sales package
  - LinkedIn proof draft when configured

- `coach_outreach`
  - LinkedIn draft or email draft

- `landing_page_copy`
  - document-style draft or newsletter-compatible draft

- `sales_one_pager`
  - package payload for design/rendering or external export

---

## Prompting And Workflow Config

Revenue workflows should extend the existing `WorkflowVersionConfig` model instead of bypassing it.

### Prompt additions

- persona notes
- offer framing
- CTA constraints
- objection handling
- proof-point priority
- tone guardrails to avoid generic sales copy

### Retrieval additions

- include revenue-winning examples
- include recent failed or rejected revenue examples
- optionally include campaign context
- optionally include partner context
- optionally include lead-stage context

### Routing additions

- `target_intent = revenue`
- target conversion goal slug
- target package kind where relevant

---

## Control-Room Revenue Screen

The control room gets a new `Revenue` page.

### Required sections

- active revenue playbooks
- recent revenue executions
- conversion goals and progress
- recent conversion events
- partner sales enablement packages
- quick-run controls for manual playbook execution

### Operator actions

- run a playbook
- inspect recent execution results
- open linked drafts in the manual queue
- mark sales packages delivered
- filter by partner, campaign, lead, persona, playbook, or status

This page is operational, not just analytical.

---

## Partner Sales Enablement

This is the blueprint gap that must be closed explicitly.

### Required partner package types

- registration push package
- ROI summary package

### Registration push package contents

- headline
- short event summary
- urgency copy
- CTA copy
- suggested email body
- suggested social support copy
- asset references if available

### ROI summary package contents

- headline
- proof summary
- impact metrics
- suggested partner talking points
- suggested outreach email copy
- optional supporting social draft links

### Provenance rules

Every sales package must preserve:

- partner slug/name
- source event id
- source event type
- related revenue playbook
- linked draft ids where relevant

---

## Conversion Tracking

Revenue analytics need explicit conversion objects, not just impressions and engagement.

### Goal examples

- event registrations
- demo requests
- follow-up replies
- partner distribution completions

### Event ingestion sources

- webhook
- CSV/import
- manual admin entry
- publisher callback or ESP callback when available later

### Analytics grouping

Conversion reporting should support:

- by revenue playbook
- by workflow
- by persona
- by partner
- by campaign
- by CTA

---

## Error Handling

### Revenue execution failures

If a revenue playbook is missing its workflow or required context:

- the execution record is still created
- status becomes `failed`
- the error is visible in the revenue screen

### Conversion ingest failures

If a conversion event is malformed or duplicated:

- reject with a clear error
- preserve the original payload when feasible
- dedupe by goal + external event id

### Partner package generation failures

If the playbook run succeeds but package generation fails:

- keep the draft/job
- mark the package record failed
- expose the failure in the partner and revenue views

---

## Testing Strategy

The implementation must add tests for:

- revenue model creation and enum persistence
- revenue playbook execution from campaign, lead, partner, and manual sources
- revenue-context propagation into prompt snapshots
- `intent = revenue` persistence on generated drafts
- conversion goal/event APIs
- revenue control-room view rendering
- sales enablement package generation and delivery status
- regression checks so partner and campaign behavior still works

The implementation should follow red-green-refactor.

---

## Success Criteria

This slice is complete when:

1. Operators can run a revenue playbook from the control room.
2. Revenue drafts enter the normal manual queue with `intent = revenue`.
3. Campaigns, leads, and partner events can all produce revenue executions through the canonical workflow engine.
4. Alliance and FSS can receive revenue-oriented sales enablement packages, not just social bundles.
5. Conversion goals and events are stored and visible in the UI.
6. Revenue history is searchable in analytics and memory by intent and playbook.
7. The implementation does not fork the architecture into a separate sales subsystem.

---

## Recommended Build Order

1. add canonical revenue models and migration
2. add revenue intent plumbing and prompt context
3. add revenue service and playbook execution
4. add sales enablement package generation
5. add revenue API routes
6. add revenue control-room page
7. add conversion ingest and reporting
8. run partner/campaign/lead regressions
