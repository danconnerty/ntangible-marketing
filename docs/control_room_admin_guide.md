# NTangible Control Room Admin Guide

## Core systems

- FastAPI app: API + server-rendered control-room UI
- Postgres: canonical workflow, trigger, review, memory, and analytics records
- Scheduler worker: `python scripts/run_scheduler.py`
- Platform publishers: X, LinkedIn, Instagram adapters
- Newsletter publisher: Mailchimp/mock adapter
- Canva renderer: asset generation for Instagram and template-driven media

## Canonical tables

- `workflows`
- `workflow_versions`
- `calendar_rules`
- `trigger_events`
- `content_jobs`
- `draft_variants`
- `review_actions`
- `assets`
- `memory_items`
- `draft_analytics_snapshots`
- `workflow_analytics_snapshots`
- `campaigns`
- `campaign_workflow_scopes`
- `campaign_runs`
- `competitor_sources`
- `competitor_observations`
- `competitor_signals`
- `lead_accounts`
- `lead_contacts`
- `lead_nurture_tasks`

## Startup checklist

1. Apply migrations: `alembic upgrade head`
2. Start the API: `uvicorn app.main:app --reload`
3. Start the scheduler in a second process: `python scripts/run_scheduler.py`
4. Seed demo data if needed: `python scripts/seed_control_room_demo.py`
5. If web auth is enabled, set:
   - `CONTROL_ROOM_REQUIRE_AUTH=true`
   - `CONTROL_ROOM_USERNAME`
   - `CONTROL_ROOM_PASSWORD`
   - `CONTROL_ROOM_SESSION_SECRET`

## Operational expectations

- The UI is the primary operator surface.
- The scheduler is responsible for:
  - firing due calendar rules
  - expiring stale manual drafts
  - publishing due scheduled manual drafts
  - publishing due automatic drafts
- Memory sync is lazy and additive. It does not delete legacy history.

## Legacy compatibility

Legacy X, LinkedIn, Instagram, and public content-brain routes still exist. They should be treated as compatibility endpoints while the control room becomes the canonical operator path.

Legacy API responses now include:
- `X-NTangible-Legacy-Endpoint: true`
- `X-NTangible-Canonical-Path: /control-room`
