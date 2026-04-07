# Phase 4: Instagram Integration + Visual Asset Pipeline — Design Spec

**Date:** 2026-04-06  
**Status:** Draft for review  
**Approach:** Canva-first parallel Instagram lane

---

## Overview

Phase 4 adds NTangible's Instagram lane to the automated marketing engine, assuming the blueprint's Phase 2 scheduler/content calendar dashboard and Phase 3 LinkedIn approval flow UI already exist.

This phase covers two coordinated outcomes:

1. **NTangible-owned Instagram automation**  
   The system generates captions, hashtags, CTA variants, rendered assets, and publish jobs for NTangible's Instagram Business account.

2. **Partner-ready Instagram packages**  
   The system generates co-branded Instagram-ready content packages for partners such as Alliance Fastpitch and Future Stars Series, but does not post on behalf of partners. Partner packages are generated automatically and routed through the existing Tier 2 review/delivery flow.

The differentiator in Phase 4 is the **visual asset pipeline**. Unlike X and LinkedIn, Instagram depends on rendered media as the primary output. This phase therefore adds both Instagram posting support and a Canva-first template rendering subsystem that future phases can reuse.

### Phase Objective

Build a production-ready Instagram workflow that:

- generates platform-specific Instagram captions and media briefs
- enforces deterministic compliance and athlete-safety rules
- renders template-driven visuals through Canva
- publishes NTangible-owned Instagram content automatically where allowed
- creates partner-delivery packages for Instagram-heavy partner content
- integrates with the existing scheduler, approval tiers, and analytics hooks

---

## 1. Platform Role

Instagram is NTangible's brand-building and athlete-facing channel. It is the most visual of the three social lanes and the blueprint states that the heaviest Instagram volume will be partner-driven.

Phase 4 therefore treats Instagram as two related but separate operating modes:

- **Owned-channel mode**  
  NTangible publishes directly to its own Instagram Business account.

- **Partner-package mode**  
  The engine generates captions, hashtags, and rendered co-branded assets for partner marketing teams to post on their own accounts.

The system must not blur these modes. NTangible-owned content can auto-publish after guardrails pass. Partner-facing packages must be generated and delivered, not directly posted by NTangible on a partner's behalf.

---

## 2. Supported Content Types

Phase 4 supports the Instagram content mix defined in the blueprint.

| Content Type | Format | Frequency | Automation Model |
|---|---|---:|---|
| Athlete Spotlight | Static graphic + caption | 2x/week | Template + auto-caption |
| Education Carousel | 5-8 slide carousel | 1x/week | Fully automated, template-driven |
| Reel / Video | 15-60 second video | 2x/week | Script automated, final production manual/semi-auto |
| Partner Content | Co-branded post | As available | Template-driven package generation |
| Stories | Polls, reposts, BTS | 3-5x/week | Semi-auto from template bank |
| Stat / Bold Statement | Single-image graphic | 1-2x/week | Fully automated, template-driven |

### In-Scope Rendered Outputs

- single-image feed post
- multi-slide carousel
- story frame set
- reel script + shot list + cover brief
- partner co-branded post package

### Explicitly Out Of Scope

- fully automated custom video editing
- partner auto-posting to partner Instagram accounts
- DM automation
- athlete UGC intake
- sports calendar ingestion
- advanced cross-platform repurposing logic

Those belong to later blueprint phases.

---

## 3. Architecture

Phase 4 uses a **parallel Instagram lane** instead of forcing a cross-platform refactor. Instagram gets its own writer, compliance runner, publisher adapters, asset-rendering service, and partner-package service, while reusing shared infrastructure from earlier phases.

### Shared Infrastructure Reused

- environment/config loading
- bearer-token API auth
- SQLAlchemy session and Postgres persistence
- brand voice and approved-claims YAML config
- deterministic factual-claim validation patterns
- scheduler/calendar integration points from Phase 2
- approval tier model and UI flow from Phase 3
- analytics hooks for later measurement

### New Instagram-Specific Components

- **Instagram Writer**  
  Generates Instagram captions, hashtag sets, CTA variants, carousel slide copy, story text, and reel briefs.

- **Instagram Compliance**  
  Applies deterministic Instagram-specific brand, factual, and safety checks.

- **Canva Asset Renderer**  
  Populates approved Canva templates and returns rendered media artifacts.

- **Instagram Publisher**  
  Publishes NTangible-owned feed posts, carousels, Stories, and Reel containers through the Instagram Graph API where supported.

- **Partner Package Service**  
  Creates reviewable partner delivery bundles containing captions, hashtags, rendered assets, and usage notes.

- **Instagram Scheduling Adapter**  
  Hands compliant, rendered posts into the already-existing scheduler/calendar layer.

### Design Boundary

- text generation belongs in Instagram agent modules
- compliance belongs in Instagram compliance modules
- media rendering belongs in the Canva pipeline
- publish/delivery belongs in publisher/package services
- scheduling/approvals remain owned by the prior roadmap phases

This keeps Phase 4 focused on Instagram and media generation rather than turning it into a full platform rewrite.

---

## 4. Workflow

### 4.1 NTangible-Owned Instagram Flow

1. Campaign Planner, manual dashboard action, or a partner/event signal creates an Instagram content request.
2. Instagram Writer generates:
   - 2-3 caption variations
   - hashtag candidates
   - CTA type
   - structured asset instructions
   - content intent tag (`brand`, `partner`, or `revenue`)
3. Instagram Compliance validates each candidate.
4. The selected candidate is converted into a render payload.
5. Canva Asset Renderer populates the required template family.
6. Scheduler assigns the post to Instagram posting windows.
7. Instagram Publisher publishes the media/caption package through the Instagram Graph API.
8. Publish identifiers are stored for later analytics collection.

### 4.2 Partner Delivery Flow

1. A partner-driven event or milestone creates a package request.
2. Writer + compliance + renderer build the Instagram-ready package.
3. The package enters **Tier 2** review.
4. Once approved, the package is delivered to partner marketing through the dashboard or configured outbound delivery channel.

### 4.3 Reel / Video Flow

1. Writer produces:
   - hook
   - talking points
   - CTA
   - shot list
   - recommended visual cues
   - caption + hashtags
2. Canva renderer generates the cover asset and creative brief attachments where applicable.
3. Video assembly remains manual or semi-auto.
4. Finished video is published through the Instagram lane once media is available.

### 4.4 Stories Flow

Stories are treated as fast-turn template-bank outputs:

- polls
- repost frames
- BTS prompts
- event snippets
- athlete/result highlights

Stories can be scheduled in high volume but should remain semiautomated rather than open-ended freeform designs.

---

## 5. Content Rules

### 5.1 Caption Structure

Instagram captions follow the blueprint formula:

- **Hook:** 1-2 punchy opening lines
- **Body:** 2-4 lines of story, insight, or proof
- **CTA:** exactly one call to action

### 5.2 Voice

Instagram voice differs from X and LinkedIn:

- bold
- visual-first
- tension-led
- hook must stand alone before "more"
- provocative but not hype-beast
- athlete-facing and emotionally legible

It should feel sharper and more visual than LinkedIn, but less hyper-reactive than X.

### 5.3 Hashtags

- 6-10 hashtags per post
- always at the end
- never mid-caption
- mix evergreen NTangible tags with topical/event-specific tags

### 5.4 CTA Rules

Exactly one CTA per post. CTA types rotate across:

- tag
- comment
- share
- visit link in bio

### 5.5 Posting Windows

Instagram scheduling should default to:

- Tuesday-Friday, 11 AM-1 PM ET
- Tuesday-Friday, 7-9 PM ET
- weekends reserved for lighter, culture-forward content

These windows are scheduler defaults, not hard constraints.

---

## 6. Visual Asset Pipeline

Phase 4 is **Canva-first**.

The system should define approved Canva template families and populate them through structured payloads. The initial objective is speed, consistency, and scale, not vendor neutrality.

### 6.1 Template Families

The initial template families are:

- `athlete_spotlight`
- `commitment_post`
- `clutch_certified`
- `event_leaderboard`
- `bold_statement`
- `education_carousel`
- `story_poll`
- `story_repost`
- `partner_event_spotlight`

### 6.2 Canva Payload Model

Every render request should include:

- template family
- concrete Canva template ID
- partner/brand mode
- text fields
- numeric/stat fields
- branding variant
- image references
- output dimensions
- output asset roles

### 6.3 Asset Render Rules

- single-image posts render one output
- carousels render 5-8 ordered slide assets
- story outputs render one or more story frames
- reel jobs render cover art and a production brief, not the final edited video

### 6.4 Failure Handling

If Canva rendering fails:

- retry transient failures
- log provider response and payload
- move item to `render_failed` or `needs_design_review`
- never publish text without its required media

### 6.5 Carousel Decision

Per approved design direction for this spec, carousels are **fully automated in Phase 4**, not designer-fallback by default. Designer fallback is reserved only for render failures, missing inputs, or invalid template payloads.

---

## 7. Data Model

### 7.1 instagram_posts

Primary queue object for NTangible-owned Instagram content.

Recommended fields:

- `id`
- `content_type`
- `intent`
- `pillar`
- `status`
- `approval_tier`
- `caption`
- `hashtags`
- `cta_type`
- `asset_type`
- `request_payload`
- `compliance_result`
- `scheduled_for`
- `published_at`
- `instagram_media_id`
- `post_url`
- `failure_reason`
- `created_at`
- `updated_at`

### 7.2 instagram_assets

Stores rendered asset outputs.

Recommended fields:

- `id`
- `instagram_post_id`
- `asset_role`
- `template_family`
- `canva_template_id`
- `render_status`
- `asset_url`
- `local_cache_path`
- `dimensions`
- `asset_metadata`
- `created_at`

### 7.3 instagram_render_jobs

Tracks Canva render attempts.

Recommended fields:

- `id`
- `instagram_post_id`
- `template_family`
- `input_payload`
- `status`
- `provider_job_id`
- `error_message`
- `started_at`
- `completed_at`

### 7.4 partner_delivery_packages

Tracks Instagram packages prepared for partner review/delivery.

Recommended fields:

- `id`
- `partner_name`
- `source_event_type`
- `approval_tier`
- `status`
- `caption`
- `hashtags`
- `delivery_channel`
- `delivery_payload`
- `review_notes`
- `delivered_at`
- `created_at`
- `updated_at`

### 7.5 instagram_generation_log

Stores Instagram prompt snapshots and generation metadata.

Recommended fields:

- `id`
- `instagram_post_id`
- `prompt_snapshot`
- `response`
- `model`
- `tokens_in`
- `tokens_out`
- `cost_estimate`
- `duration_ms`
- `created_at`

---

## 8. Approval And Delivery Rules

Phase 4 follows the blueprint's approval model.

### Tier 1: Full Auto-Publish

Default for NTangible-owned Instagram content:

- athlete spotlights on NTangible channels
- stat cards
- bold-statement graphics
- education carousels
- stories
- reel briefs once final media is ready

These pass through brand compliance and publish automatically.

### Tier 2: Partner Delivery Review

Default for partner-facing Instagram packages:

- Alliance/FSS co-branded content
- event-ready graphics for partner channels
- commitment post packages destined for partner marketing teams

These are auto-generated but held for dashboard review before delivery.

### Tier 3: Rare Full Review

Reserved for:

- investor-facing content
- legal-sensitive posts
- crisis-response material

These should remain rare.

---

## 9. Compliance And Guardrails

Phase 4 inherits all existing brand/factual rules and adds Instagram-specific ones.

### 9.1 Shared Brand And Claim Guardrails

- banned phrase rejection
- trademark enforcement
- restricted client blocking
- approved-claim key validation
- text-level claim verification
- undeclared numeric blocking

### 9.2 Instagram-Specific Guardrails

- caption must follow hook -> body -> CTA structure
- 6-10 hashtags max
- hashtags must appear at the end
- only one CTA
- caption voice must match Instagram's visual-first tone

### 9.3 Visual/Citation Consistency

Asset text and caption text must agree.

If the rendered graphic includes:

- a percentage
- a score tier
- a named athlete milestone
- a partner/event numeric claim

then the caption and claim metadata must reference the same approved values.

### 9.4 Athlete Score Publishing Rule

Athlete-specific content must respect the blueprint's positive-only score rule.

Implications:

- low or unflattering athlete scores must never render into public assets
- athlete spotlight generation must check score eligibility before render
- aggregate/anonymized content can use broader distributions, but individual athlete graphics are positive-only

### 9.5 Template Safety

Only approved Canva templates and approved branding variants are allowed in automation.

The system must block:

- unapproved partner brand usage
- ad hoc template IDs
- asset families missing required approval metadata

---

## 10. Publishing And Integration

### 10.1 Instagram API Integration

Phase 4 uses the Instagram Graph API via Meta Business Suite.

Requirements from the blueprint:

- Instagram Business account
- linked Facebook Page
- approved Meta app/auth setup

The publisher should support:

- feed posts
- carousel posts
- Stories
- Reel-ready publication paths where supported by the active account/app setup

### 10.2 Scheduler Integration

Phase 4 assumes Phase 2 already provides:

- calendar slots
- scheduling status
- pause/resume controls
- dashboard visibility

Instagram items should plug into that system rather than invent their own scheduling engine.

### 10.3 Approval UI Integration

Phase 4 assumes Phase 3 already provides:

- approval queue concepts
- Tier 2/Tier 3 review flow
- inline review notes

Instagram partner packages and sensitive Instagram posts should use that same approval surface.

### 10.4 Analytics Hooks

Phase 4 should store enough metadata for later analytics work:

- Instagram media IDs
- published URLs
- scheduled vs actual publish time
- template family
- content intent tag
- partner/owned mode

Phase 4 does not need to build the full analytics agent. It only needs to emit the right data hooks for Phase 6.

---

## 11. Error Handling

### Generation Failure

- bounded retries
- clear failure reason
- preserve prompt snapshot and raw model response

### Compliance Failure

- regenerate within bounded attempts
- log exact failed check
- fail closed if requirements cannot be satisfied

### Render Failure

- retry transient Canva errors
- record provider payload and error body
- move to `render_failed` or `needs_design_review`

### Publish Failure

- deterministic failures -> `failed`
- ambiguous Meta API results -> `publishing_unknown`
- never auto-retry ambiguous publish outcomes if duplicate posting is possible

### Partner Delivery Failure

- preserve rendered package
- mark delivery failure explicitly
- never discard usable assets because delivery channel failed

---

## 12. API Surface

The exact endpoint naming can follow existing platform conventions, but Phase 4 needs APIs for:

- create/generate Instagram content request
- list draft/scheduled Instagram posts
- inspect a single Instagram post and its assets
- approve/reject partner packages
- publish owned Instagram posts
- resolve ambiguous publish outcomes
- list partner delivery packages
- re-render an asset when template data changes

Partner-package endpoints and owned-channel endpoints should be explicit, not overloaded into one ambiguous resource model.

---

## 13. Testing Strategy

Phase 4 should ship with tests for:

- Instagram prompt generation by content type
- Instagram compliance rules
- Canva payload construction by template family
- render-job state transitions
- publisher state transitions for owned Instagram posts
- partner delivery package generation
- athlete-score safety enforcement
- end-to-end smoke paths:
  - generate -> comply -> render -> schedule -> publish
  - generate -> comply -> render -> review -> deliver package

Fixture coverage should include:

- athlete spotlight
- commitment graphic
- event leaderboard
- bold statement
- education carousel
- story poll
- partner event spotlight

---

## 14. Acceptance Criteria

Phase 4 is complete when:

- NTangible-owned Instagram content can be generated, rendered, scheduled, and published through the Instagram lane
- partner-ready Instagram packages can be generated and routed into Tier 2 review/delivery
- Canva templates render approved single-image, carousel, and story assets automatically
- reel briefs and cover assets are generated automatically
- athlete-score and claim guardrails are enforced before any asset is published or delivered
- Instagram artifacts integrate with the existing scheduler and approval systems assumed by the blueprint
- publish/delivery failures are visible, recoverable, and non-destructive

---

## 15. Non-Goals

Phase 4 does not attempt to solve:

- partner API ingestion
- event-triggered partner content orchestration at full scale
- analytics optimization loops
- content repurposing engine
- UGC submission pipeline
- newsletter/blog generation
- competitor monitoring
- lead nurture

Those remain later phases in the blueprint.
