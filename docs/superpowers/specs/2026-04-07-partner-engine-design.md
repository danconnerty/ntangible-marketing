# Partner Engine Design

**Date:** 2026-04-07  
**Status:** Approved for implementation  
**Scope:** Alliance + FSS partner engine, end to end

---

## Goal

Add the missing partner-driven side of the NTangible blueprint so Alliance and FSS can both:

- send real partner events through webhooks and a partner portal
- generate routed content through the canonical workflow engine
- produce partner delivery packages for review and export
- appear in a dedicated partner hub inside the control room
- preserve partner intent and provenance across drafts, analytics, and history

---

## Product Outcome

The partner engine is one integrated subsystem, not a side app.

It extends the existing control-room architecture with five outcomes:

1. **Partner intake**
   Alliance and FSS can submit partner data through:
   - authenticated webhook endpoints
   - a partner-facing submission portal

2. **Partner normalization**
   Raw partner payloads are converted into canonical event records and routed into the existing trigger engine.

3. **Partner distribution logic**
   Each event type is routed to the correct platforms and content types using partner-aware rules.

4. **Partner delivery**
   Generated content becomes partner-ready delivery bundles with:
   - caption/copy
   - hashtags
   - related assets
   - usage notes
   - delivery state

5. **Partner hub**
   Operators can monitor partner events, package status, routing failures, and manual re-runs from a dedicated control-room page.

---

## In Scope

### Partners

- Alliance Fastpitch
- Future Stars Series (FSS)

### Event Types

- `assessment_completed`
- `leaderboard_published`
- `commitment_update`
- `offer_update`
- `milestone_reached`
- `registration_push`
- `event_promotion`

### Surfaces

- authenticated webhook intake
- partner-facing portal login + submission UI
- control-room partner hub
- package generation and delivery tracking
- canonical storage for partner events and bundles

---

## Out Of Scope

- partner auto-posting to partner-owned social accounts
- CRM or billing
- advanced partner user management beyond a basic portal login
- fully custom workflow builder for partner routing rules

These can come later without changing the core model.

---

## Architecture

The partner engine stays inside the modular monolith and reuses the control-room pipeline:

```text
partner webhook / portal
-> partner intake service
-> canonical partner event record
-> partner routing service
-> trigger engine
-> workflow engine
-> draft variants
-> partner delivery bundle builder
-> partner hub + partner portal package views
```

### New canonical records

- `PartnerAccount`
- `PartnerEventRecord`
- `PartnerDeliveryBundle`

### Existing systems reused

- `TriggerEvent`
- `Workflow` / `WorkflowVersion`
- `ContentJob`
- `DraftVariant`
- `Asset`
- scheduler
- analytics
- review queue

---

## Data Model

### PartnerAccount

Stores partner-level settings:

- slug and display name
- active flag
- portal username/password
- webhook secret
- supported event types
- routing configuration
- delivery defaults

### PartnerEventRecord

Stores every ingested partner event, before and after normalization:

- partner account
- intake source: `webhook`, `portal`, `manual`
- event type
- external event id
- raw payload
- normalized payload
- processing status
- related trigger ids
- failure reason

### PartnerDeliveryBundle

Stores the reviewed/exportable package created from a partner-triggered draft:

- partner account
- source event record
- draft variant
- platform
- status
- headline / caption
- hashtags
- asset ids
- delivery payload
- usage notes
- delivered timestamp

---

## Routing Rules

Routing is event-type driven and partner-aware.

### Shared rules

- all partner-generated drafts must persist `intent = partner`
- all partner-generated drafts must preserve partner provenance in trigger and job snapshots
- partner content enters manual review by default

### Platform distribution

- `assessment_completed`
  - X data drop
  - LinkedIn data insight
  - Instagram partner package

- `leaderboard_published`
  - X data drop
  - LinkedIn data insight
  - Instagram partner package

- `commitment_update`
  - X data drop
  - Instagram commitment package

- `offer_update`
  - X data drop
  - Instagram commitment package

- `milestone_reached`
  - X data drop
  - LinkedIn company/data update
  - Instagram partner package

- `registration_push`
  - X trend/hype post
  - LinkedIn company update
  - Instagram partner package

- `event_promotion`
  - X trend/hype post
  - LinkedIn company update
  - Instagram partner package

---

## Partner Portal

The partner portal is a lightweight authenticated experience.

### Required pages

- login
- submit event
- recent submissions
- delivery packages

### Submission behavior

Partners choose an event type and submit the associated fields.
The portal writes a `PartnerEventRecord`, runs normalization/routing, and shows the resulting status.

---

## Control-Room Partner Hub

The control room gets a new `Partners` screen showing:

- partner accounts
- recent partner events
- routing status
- generated bundles
- failed ingests
- package review/delivery state
- regenerate / rerun actions

This is the operator view. The partner portal is the external submission view.

---

## Intent Tagging

Partner-generated content must be first-class in the canonical system.

That means partner-derived drafts/jobs/bundles must preserve:

- `intent = partner`
- partner slug/name
- source event type
- source event id
- intake source

This metadata must be visible in:

- manual queue
- trigger feed
- brain/history
- analytics
- partner hub

---

## Delivery Package Rules

Every partner bundle should include:

- partner name
- event type
- platform
- caption/copy
- hashtags
- related asset links
- delivery/export payload
- operator notes

Bundles are not direct publishes to partner accounts.
They are reviewed and then marked delivered/exported.

---

## Testing

Add tests for:

- webhook intake
- portal auth and submissions
- partner routing for all event types
- partner bundle creation
- partner hub web views
- partner portal web views
- partner intent persistence

---

## Success Criteria

This slice is complete when:

1. Alliance and FSS can both submit all supported event types through webhook and portal paths.
2. Each event creates canonical partner records and routed triggers.
3. Partner drafts preserve intent/provenance through the control-room pipeline.
4. Delivery bundles are generated and visible.
5. The control-room partner hub and partner portal both work.
6. Tests are green.
