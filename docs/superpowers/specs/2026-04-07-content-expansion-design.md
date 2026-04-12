# Content Expansion Design

**Date:** 2026-04-07  
**Status:** Approved at design level, pending implementation  
**Scope:** repurposing engine, blog/SEO, science credibility, video briefs, UGC pipeline, sports calendar, and their canonical control-room integration

---

## Goal

Complete the third remaining blueprint bucket by turning the existing content-expansion modules into one coherent, canonical control-room slice.

This wave is not about inventing a second app. It is about:

- finishing the remaining placeholder services
- mounting already-built APIs and web views into the main app
- making the modules discoverable from the control room
- preserving the existing manual-first workflow, workflow engine, review queue, history, and analytics model

---

## Product Outcome

After this slice:

1. operators can access `blog`, `science`, `video`, `ugc`, `repurposing`, and `sports` from the same control-room product
2. every expansion workflow still routes through canonical `TriggerEvent -> Workflow -> ContentJob -> DraftVariant`
3. repurposing and UGC stop being half-finished modules and become real, operator-usable systems
4. the control-room UI exposes one clear “content expansion” area instead of relying on orphan routes
5. the blueprint’s third implementation bucket is structurally complete

---

## What Already Exists

The repo already contains substantial implementation for several expansion lanes:

- `BlogService` and blog API routes
- `ScienceCredibilityService` and science API routes
- `VideoContentService` plus API and web routes
- `SportsCalendarService` plus API and web routes
- `UGCService`
- `RepurposingService`
- templates for `blog`, `science`, `video`, `ugc`, `repurposing`, and `sports`

The gap is not “build everything from zero.” The gap is that these pieces are unevenly integrated into the main control-room application.

Current problems:

- some expansion routers are not mounted in [app/main.py](/Users/elliot18/Desktop/Home/Projects/ntangible_marketing/app/main.py)
- `blog`, `science`, and `repurposing` have API-only routes but no canonical control-room GET page
- the top-level control-room nav does not expose the expansion family
- there is no expansion hub tying these modules together as one product area

---

## In Scope

### Module Integration

- mount canonical API routers for:
  - blog
  - science
  - repurposing
  - video
  - ugc
  - sports

### Web Surfaces

- add canonical control-room pages for:
  - `/control-room/blog`
  - `/control-room/science`
  - `/control-room/repurposing`
- keep existing:
  - `/control-room/video`
  - `/control-room/ugc`
  - `/control-room/sports`

### Expansion Hub

- add `/control-room/expansion`
- expose counts and quick links for all expansion modules
- add the hub to the main control-room navigation

### Final Wiring

- make all expansion templates use mounted control-room routes cleanly
- ensure API HTMX flows and web views are consistent
- add main-app route coverage and expansion UI tests

---

## Out Of Scope

- redesigning the workflow engine
- replacing the control-room shell
- changing manual-first review semantics
- full CMS/editor UX for blog beyond the current draft/publish pattern
- advanced video rendering or automated final-edit generation
- a second navigation framework or standalone frontend app

---

## Architecture

The correct shape is:

```text
Control Room
├── Dashboard
├── Activity
├── Workflows
├── Analytics
├── Revenue
├── Expansion
│   ├── Blog
│   ├── Science
│   ├── Video
│   ├── UGC
│   ├── Repurposing
│   └── Sports
└── Status
```

Each expansion lane remains its own focused module, but they are grouped under one operator-facing surface because they are all “content expansion” features in the blueprint.

### Why this approach

- it preserves clear module boundaries
- it avoids one giant “content lab” service
- it makes the control room feel like one product
- it minimizes code churn because existing services and templates are reused

---

## Control-Room Integration Rules

### 1. Expansion modules remain canonical workflow clients

Expansion features must keep generating work through the existing workflow stack, not bypass it with bespoke job tables or direct publisher shortcuts.

### 2. The hub is a discovery surface, not a second dashboard

`/control-room/expansion` should summarize and link to modules. It should not duplicate the main dashboard.

### 3. Existing route shapes should be preserved where already good

If a route module already provides a strong API or web shape, integrate it rather than rewriting it into a new abstraction.

### 4. Module-specific pages stay thin

Each page should:

- load dashboard data from its service
- render the existing template
- use HTMX/API posts that already exist or are added in that module

They should not re-implement business logic in the web layer.

---

## Integration Details By Module

### Blog

Keep blog generation and publication in `BlogService`, but add a canonical control-room GET page and mount the API router in the main app.

Expected operator flow:

- open blog page
- generate a draft
- review the article list
- publish through the configured CMS publisher

### Science

Keep science generation in `ScienceCredibilityService`, add a canonical GET page, and mount the API router.

Expected flow:

- choose advisor spotlight / white paper excerpt / milestone
- generate through the workflow engine
- review result and records

### Video

The video web/API routes already exist. Main work is mounting them and exposing them from the expansion hub.

### UGC

The UGC pipeline is already implemented but must be treated as a first-class expansion lane by mounting the existing API/web routes and surfacing it through the hub.

### Repurposing

Repurposing already has service logic and API routes, but it still needs a canonical control-room GET page and main-app mounting.

### Sports

Sports already has API and web routes. Main work is mounting and exposing it as part of the unified expansion surface.

---

## UI Design

### Top Nav

Add one new top-level tab:

- `Expansion`

Do not add six new top-level tabs; that makes the nav noisy and brittle.

### Expansion Hub

The hub should show one card per module:

- Blog
- Science
- Video
- UGC
- Repurposing
- Sports

Each card should include:

- module title
- one-sentence purpose
- lightweight count summary
- primary CTA link

### Module Pages

Use the existing templates with minimal changes. They already reflect the intended module-specific operator workflows.

---

## Testing Strategy

This slice is mostly integration, so the primary tests should be:

- route registration in `app.main`
- web view rendering for new module pages
- expansion hub rendering
- regression coverage that the full app still boots and serves canonical routes

No large new algorithmic test matrix is needed unless implementation uncovers actual service gaps.

---

## Success Criteria

This slice is complete when:

- the main app mounts all expansion APIs and web routes
- the control room exposes a usable `Expansion` hub
- `blog`, `science`, `video`, `ugc`, `repurposing`, and `sports` are reachable through canonical control-room routes
- existing templates render through the main app
- regression tests prove route registration and view rendering

This makes the third major blueprint bucket operationally complete without forcing a redesign of already-good module internals.
