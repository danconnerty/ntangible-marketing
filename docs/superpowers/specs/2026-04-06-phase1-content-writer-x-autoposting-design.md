# Phase 1: Content Writer Agent + X Auto-Posting — Design Spec

**Date:** 2026-04-06
**Status:** Approved (revised after review)
**Approach:** Modular Monolith (Approach A)

---

## Overview

Phase 1 of the NTangible Automated Marketing Engine. A standalone Python system that uses Claude to generate on-brand single tweets, runs them through a deterministic brand compliance gate with factual claim verification, stores them as drafts, and publishes to X (Twitter) on manual approval via a protected API.

The core loop is: **generate → validate → approve → publish**. No autonomous scheduling (Phase 2), no partner data triggers (Phase 5), no dashboard UI (Phase 2). API-only with curl/Postman.

### Stack

- **Language:** Python 3.12+
- **Framework:** FastAPI + Uvicorn
- **LLM:** Claude (Anthropic SDK)
- **Database:** PostgreSQL (via SQLAlchemy + Alembic)
- **X API Client:** Tweepy (official) / Twikit (free, dev) / Mock (testing)
- **Config:** YAML files for brand voice, content pillars, platform rules
- **Hosting:** Railway (FastAPI app + managed Postgres)
- **Auth:** Bearer token (API key from env var, checked on every endpoint)

---

## 1. Content Writer Agent

The module that calls Claude to generate tweets.

### Input

A content request containing:
- `content_type`: hot_take | data_drop | trend_jack (threads deferred to Phase 2 — partial-failure recovery is complex)
- `pillar`: blind_spot | cost_of_guessing | client_proof | thought_leadership | product
- `claims` (optional): list of approved_claims keys to reference (e.g., `["cf_all_american", "assessment_count"]`)
- `context` (optional): trending topic or additional framing

### Prompt Assembly

Each Claude API call is built from:
1. **System prompt** with NTangible brand voice rules (punchy, contrarian, sports bar meets data lab, never sounds like a brand account)
2. **Platform constraints** (280 chars max, 1-2 hashtags max)
3. **Content pillar guidance** with example angles from config
4. **Banned phrases list** injected directly
5. **Trademark rules** (Clutch Factor(TM), NTangible Score, The Pressure Test)
6. **Approved claims** — only verified facts from `approved_claims.yaml` may be cited. The prompt injects the specific claims requested. Claude is instructed: "Do not invent statistics, percentages, client names, or outcomes. Use only the approved claims provided."
7. **Optional context** (trending topic, additional framing)
8. **Historical top-performing hooks** (empty in Phase 1 — populated by analytics agent in Phase 6)

### Output

Claude returns structured JSON:

```json
{
    "content": "The tweet text",
    "content_type": "hot_take",
    "pillar": "cost_of_guessing",
    "claim_keys_used": ["failed_transfer_cost"],
    "hashtags": ["#TransferPortal"],
    "media_needed": false,
    "intent": "revenue"
}
```

The `claim_keys_used` field declares which approved claims the tweet references. The compliance gate runs two checks:

1. **Key-level:** `claim_keys_used` must be a subset of the `claims` requested in the API call, and each key must exist in `approved_claims.yaml`.
2. **Text-level:** For each declared claim key, verify at least one variant from each `check_value_groups` entry appears in the tweet. If the tweet says "$200K" but the approved claim says "$150K", the draft is rejected.
3. **Undeclared numerics:** Extract all claim-like numeric tokens from the tweet and verify every one is covered by a declared claim's `check_value_groups`. Extraction uses a tokenizer (not a single regex) that:
   - **Matches:** `$X`, `X%`, `XK`, `XM`, `XB`, `$X.XM`, `X,XXX`, `X,XXX+` — any token that asserts a quantity, cost, or statistical figure
   - **Ignores:** ordinals (`1st`, `2nd`, `3rd`), labels (`D1`, `D2`, `D3`), hashtag numbers (`#1`), dates and times, and bare single digits not attached to a unit
   - Implementation: split the tweet into tokens, classify each as `claim_numeric`, `ordinal`, `label`, or `plain`, then verify all `claim_numeric` tokens are covered

   Any uncovered `claim_numeric` token rejects the draft. This prevents invented stats alongside legitimate ones, without false-flagging "1st round" or "D1."

Each approved claim in `approved_claims.yaml` includes `check_value_groups` — a list of value groups where each group is a list of acceptable spelling variants (see Section 5).

### Behavior

- Generates 2-3 variations per request. All variations are returned to the user via the API — the user picks which one to publish. No random selection.
- Stateless — each call gets the full context injected, no conversation memory between generations.
- Does NOT do compliance checking, scheduling, or posting.

---

## 2. Brand Compliance Gate

Runs on every draft before it enters the publish queue. Purely deterministic — no LLM calls. Fast and predictable.

### Checks (in order)

| Check | Rule | On Failure |
|-------|------|------------|
| Banned phrases | Reject if contains any phrase from banned list | Auto-regenerate |
| Trademark enforcement | "Clutch Factor" must have (TM), correct capitalization on "NTangible Score", "The Pressure Test" | Auto-correct (regex replacement, no regeneration) |
| Client references | Hard block on restricted names (Florida A&M, Swarthmore, Sporting KC). Only verified clients may be named. | Kill draft, regenerate |
| Factual claims (key) | `claim_keys_used` must be a subset of the `claims` requested in the API call, and each key must exist in `approved_claims.yaml`. | Kill draft, regenerate |
| Factual claims (text) | For each declared claim key, verify at least one variant from each `check_value_groups` entry appears in the tweet text. Catches the model writing the wrong number. | Kill draft, regenerate |
| Undeclared numerics | Extract all numeric tokens ($X, X%, X,XXX, XM, XK) from the tweet. Every extracted value must be covered by a `check_value_groups` entry from a declared claim. Any uncovered number is rejected as an unsupported factual assertion. | Kill draft, regenerate |
| Tone check | No passive voice, no exclamation points (except rare), no fluffy motivational language, no corporate buzzwords | Auto-regenerate |
| Character limits | Single tweet <= 280 chars | Auto-regenerate with tighter constraint |
| Hashtag limits | Max 2 per tweet | Auto-trim excess hashtags |

**Deferred to Phase 5 (partner data integration):** Score threshold check. Requires a backing athlete data source with score lookups — not implementable until partner APIs are connected. In Phase 1, the content writer prompt instructs Claude not to reference specific athlete scores.

**Deferred to Phase 2:** Thread support. Partial thread failures (tweet 3 fails but tweets 1-2 are live) and ambiguous API results (X accepted the post but the local call timed out) require reconciliation logic that adds complexity beyond Phase 1 scope. Phase 1 is single tweets only.

### Regeneration Logic

- On failure, content writer is called again with the failure reason appended to the prompt.
- Max 3 regeneration attempts per content request.
- After 3 failures, item is stored as `failed` with the compliance errors logged. Requires manual intervention.

### Implementation

- Banned phrases and client blocklist are config files (updatable without code changes).
- Trademark corrections are regex replacements.
- Tone check uses simple heuristics (passive voice regex patterns, exclamation count, buzzword list) — not an LLM call. Upgradeable to LLM-based tone scorer in a later phase.

---

## 3. Content Queue & Publishing

Stores generated drafts and publishes them on manual approval.

### Content Queue (Postgres)

```
content_queue
  id                  uuid, pk
  content             text
  content_type        enum: hot_take, data_drop, trend_jack
  pillar              enum: blind_spot, cost_of_guessing, client_proof, thought_leadership, product
  intent              enum: brand, partner, revenue
  hashtags            text[]
  status              enum: draft, publishing, published, publishing_unknown, failed, rejected
  variant_group       uuid (groups the 2-3 variations from a single generation request)
  request_payload     jsonb (the original generation request: content_type, pillar, claims, context — used by /regenerate)
  expires_at          timestamptz, nullable (set for trend_jack content — auto-expires stale reactive drafts)
  published_at        timestamptz, nullable
  post_url            text, nullable
  tweet_id            text, nullable
  compliance_result   jsonb
  regeneration_count  int, default 0
  failure_reason      text, nullable
  created_at          timestamptz
  updated_at          timestamptz
```

### Phase 1 Flow (No Autonomous Scheduling)

1. User calls `POST /content/generate` with content_type, pillar, optional claims and context
2. Content writer generates 2-3 variations, compliance gate validates each
3. All passing drafts are stored with `status = draft`, linked by `variant_group`
4. User reviews all variants via `GET /content/drafts`
5. User picks one and publishes via `POST /content/{id}/publish` — publishes to X immediately
6. Remaining variants in the group are auto-set to `rejected`
7. Post URL and tweet ID are written back to the published row

No cron jobs. No scheduled posting windows. No cadence-based auto-generation. The user decides when to generate and when to publish. Autonomous scheduling (cadence rules, posting windows, daily generation cron) moves to Phase 2.

**Trend jack freshness:** `trend_jack` drafts are auto-assigned `expires_at = created_at + 60 minutes`. The publish endpoint rejects expired drafts with a 410 Gone response. This prevents publishing stale reactive content after the moment has passed. Other content types have no expiry.

### Publish Safety

Publishing claims the entire variant group atomically to prevent two variants from the same generation being published:

```sql
-- In a single transaction:
-- 1. Claim the selected draft AND reject all siblings atomically
UPDATE content_queue
SET status = CASE
      WHEN id = :id THEN 'publishing'
      ELSE 'rejected'
    END,
    updated_at = now()
WHERE variant_group = (SELECT variant_group FROM content_queue WHERE id = :id)
  AND status = 'draft'
RETURNING id, status
```

If the selected row is not in the returned set with `status = 'publishing'`, it was already claimed or rejected — return a 409 Conflict. This prevents concurrent publish calls on different variants from the same group from both succeeding.

### State Transition Matrix

Every endpoint checks the current status before acting. Any transition not in this table returns 409 Conflict.

| Current Status | Allowed Actions | Resulting Status |
|---|---|---|
| `draft` | publish | `publishing` → `published` or `publishing_unknown` or `failed` |
| `draft` | delete | row deleted |
| `draft` | regenerate | siblings deleted, new `draft` rows created |
| `publishing` | (internal only — X API call in progress) | `published`, `publishing_unknown`, or `failed` |
| `publishing_unknown` | resolve(published) | `published` |
| `publishing_unknown` | resolve(failed) | `failed` |
| `published` | (terminal — no actions) | — |
| `failed` | regenerate | siblings deleted, new `draft` rows created |
| `failed` | delete | row deleted |
| `rejected` | (terminal — no actions) | — |

Key constraints:
- `publishing_unknown` blocks everything except `resolve`. No delete, no regenerate, no re-publish. The tweet may be live — you must check X first.
- `publishing` is transient — set at the start of the X API call, resolved within the same request. Never persisted across requests except on crash (which transitions to `publishing_unknown` on next startup).
- `rejected` is terminal. Sibling variants rejected when another variant is published.

### API Endpoints

All endpoints require `Authorization: Bearer <API_KEY>` header. API key is set via `API_KEY` env var.

- `POST /content/generate` — generate 2-3 draft variations (content_type, pillar, optional claims, context)
- `GET /content/drafts` — list drafts awaiting review
- `GET /content/{id}` — view single item with compliance result
- `POST /content/{id}/publish` — publish this draft to X immediately (rejects sibling variants)
- `DELETE /content/{id}` — discard a draft
- `POST /content/{id}/regenerate` — discard current variants, generate a new set using the stored `request_payload`

Drafts are immutable in Phase 1. If you don't like any variant, regenerate. Free-form editing is deferred — it breaks the claim verification chain (edited text can't be deterministically proven against approved claims without re-running the full generation + compliance pipeline).
- `POST /content/{id}/resolve` — resolve a `publishing_unknown` item (outcome: published | failed, optional tweet_url)
- `GET /content/published` — list published posts with tweet URLs
- `GET /system/status` — health check, post counts

---

## 4. X Publisher

Posts to X. Swappable implementation behind a common interface.

### Interface

```python
class BasePublisher:
    def post_tweet(self, text, media=None) -> PostResult
    def delete_tweet(self, tweet_id) -> bool
```

Phase 1 is single tweets only. `post_thread` is added in Phase 2 with proper partial-failure reconciliation.

### Implementations

| Implementation | Cost | Mechanism | Use case |
|---|---|---|---|
| MockPublisher | $0 | Logs to console/DB, returns fake URL | Development and testing |
| TwikitPublisher | $0 | Session cookies, no API key | **Dev/test only** — violates X ToS, not for production |
| TweepyPublisher | $0-200/mo | Official X API v2, OAuth2 PKCE | **Production** — only official option for live posting |

Active implementation controlled by env variable: `X_PUBLISHER=mock|twikit|tweepy`

### Error Handling

- **Rate limited (429):** retry with exponential backoff (30s, 60s, 120s), max 3 retries
- **Auth failure (401/403):** log error, mark as `failed`, do not retry (broken credentials won't self-heal)
- **Definite failure (4xx other than 429):** mark as `failed` with error message, no retry
- **Timeout / network error / ambiguous response:** mark as `publishing_unknown`. Do NOT auto-retry — the tweet may already be live on X. Requires manual reconciliation: user checks X, then calls `POST /content/{id}/resolve` with `outcome: published | failed`.
- **Server error (5xx):** mark as `publishing_unknown` (X may have processed the request before returning the error)

The `publishing_unknown` state exists because a single-tweet publish can succeed on X but time out locally. Auto-retrying would double-post. The user must verify and resolve.

### PostResult

```json
{
    "success": true,
    "tweet_id": "1234567890",
    "tweet_url": "https://x.com/ntangible/status/1234567890",
    "posted_at": "2026-04-06T12:00:00Z"
}
```

---

## 5. Configuration & Brand Voice

Brand identity in code. YAML files, version controlled, updatable without touching Python.

### brand_voice.yaml

```yaml
voice:
  personality: "Punchy. Contrarian. Sports bar meets data lab."
  do:
    - "Sound like a smart person who works in sports, not a brand account"
    - "Use short, direct sentences"
    - "Lead with data-backed claims"
    - "Be opinionated — take a position"
  dont:
    - "No passive voice"
    - "No exclamation points (except rare genuine excitement)"
    - "No fluffy motivational language"
    - "No corporate buzzwords"
    - "Never sound like a press release"

banned_phrases:
  - "unlock insights"
  - "leverage data"
  - "empower your team"
  - "game-changing"
  - "cutting-edge"

trademarks:
  "Clutch Factor(TM)": ["Clutch Factor", "clutch factor", "ClutchFactor"]
  "NTangible Score": ["ntangible score", "Ntangible score"]
  "The Pressure Test": ["the pressure test", "pressure test"]

restricted_clients:
  hard_block: ["Florida A&M", "FAMU", "Swarthmore", "Sporting KC"]
  generic_only: ["MLS"]

verified_clients:
  - "Michigan State"
  - "Hofstra"
  - "Boston College"
  - "Alliance Fastpitch"
  - "Future Stars Series"
  - "RFK Racing"
  - "High Level Throwing"

score_publishing:  # Deferred to Phase 5 — no athlete data source in Phase 1
  min_threshold: 750
  allow_aggregate_full_range: true
```

### content_pillars.yaml

```yaml
pillars:
  blind_spot:
    description: "You're evaluating half the picture"
    example_angles:
      - "You measure arm strength, speed, GPA. What about pressure?"
      - "Film tells you what happened. Not what happens when it counts."

  cost_of_guessing:
    description: "The financial cost of not measuring mental performance"
    note: "All dollar amounts and percentages must come from approved_claims.yaml"
    example_angles:
      - "You're guessing on half the recruiting decision"
      - "What does it cost when the transfer doesn't work out?"

  client_proof:
    description: "Real programs using NTangible, real results"
    note: "Only reference verified_clients. Specific outcomes must be in approved_claims.yaml"
    example_angles:
      - "D1 programs are measuring what matters"
      - "The data speaks for itself"

  thought_leadership:
    description: "NTangible's position in the mental performance conversation"
    example_angles:
      - "Personality profiles don't predict performance under pressure"
      - "Coach Alignment Index — the feature nobody else has"

  product:
    description: "What NTangible does and how it works"
    note: "Specific numbers must come from approved_claims.yaml"
    example_angles:
      - "Not a survey. A validated cognitive assessment."
      - "We measure what happens when it counts."
```

### approved_claims.yaml

Verified facts the content writer may cite. Every numeric claim, percentage, dollar amount, or client outcome in a published tweet must trace back to an entry here. The compliance gate checks generated content against this list.

```yaml
# Each check_value_groups entry is one numeric fact. The inner list contains
# acceptable spelling variants — at least one variant from each group must
# appear in the tweet text if this claim is declared.
claims:
  cf_all_american:
    text: "73% of athletes scoring above 800 CF were named All-American"
    check_value_groups:
      - ["73%"]           # the percentage
      - ["800"]           # the CF threshold
    source: "NTangible internal dataset"
    verified_date: "2026-03-01"

  failed_transfer_cost:
    text: "The average failed D1 transfer costs $150K"
    check_value_groups:
      - ["$150K", "$150,000", "150K"]  # any spelling of the dollar amount
    source: "Industry research"
    verified_date: "2026-01-15"

  draft_bust_cost:
    text: "Average 1st round draft bust: -$3.5M"
    check_value_groups:
      - ["$3.5M", "$3.5 million", "3.5M"]
    source: "Industry research"
    verified_date: "2026-01-15"

  youth_churn_cost:
    text: "Youth churn: -$50K lifetime value"
    check_value_groups:
      - ["$50K", "$50,000", "50K"]
    source: "NTangible internal estimate"
    verified_date: "2026-02-01"

  assessment_count:
    text: "6,000+ assessments. 1M+ data points. 7 sports."
    check_value_groups:
      - ["6,000", "6000"]     # assessment count
      - ["1M", "1,000,000"]   # data points
      - ["7 sports"]          # sport count
    source: "NTangible platform metrics"
    verified_date: "2026-03-15"

  alliance_athlete_count:
    text: "30,000+ athletes assessed through Alliance Fastpitch"
    check_value_groups:
      - ["30,000", "30000", "30K"]
    source: "Alliance Fastpitch partnership"
    verified_date: "2026-03-01"
```

New claims are added here as they're verified. The content writer prompt receives only the claims explicitly requested in the API call. Claude is instructed not to invent or extrapolate beyond what's provided.

### platforms/x.yaml

```yaml
x:
  single_tweet_max_chars: 280
  max_hashtags: 2
  # Thread support, posting_windows, and cadence rules are Phase 2
```

---

## 6. Data Model

### Tables

**content_queue** — described in Section 3.

**generation_log** — every Claude API call for debugging and cost tracking:

```
generation_log
  id                uuid, pk
  content_queue_id  fk (nullable — null if draft was killed before queuing)
  prompt_snapshot   text (full prompt sent to Claude)
  response          jsonb (Claude's raw response)
  model             text (e.g., "claude-sonnet-4-6")
  tokens_in         int
  tokens_out        int
  cost_estimate     decimal
  duration_ms       int
  created_at        timestamptz
```

---

## 7. Project Structure

```
ntangible_marketing/
  app/
    __init__.py
    main.py                  <- FastAPI app, startup/shutdown, auth dependency
    config.py                <- Loads settings from env + YAML files
    database.py              <- SQLAlchemy engine, session factory
    agents/
      __init__.py
      content_writer.py      <- Claude API calls, prompt assembly
      compliance.py          <- Banned phrases, trademarks, tone check
    publishers/
      __init__.py
      base.py                <- BasePublisher interface
      mock.py                <- MockPublisher (dev/test)
      twikit_pub.py          <- TwikitPublisher (free, ToS risk)
      tweepy_pub.py          <- TweepyPublisher (official API)
    models/
      __init__.py
      content.py             <- SQLAlchemy models: ContentQueue, GenerationLog
    api/
      __init__.py
      routes.py              <- FastAPI routes (all require bearer token)
    config_data/
      brand_voice.yaml
      content_pillars.yaml
      approved_claims.yaml
      platforms/
        x.yaml
  tests/
    test_content_writer.py
    test_compliance.py
    test_publisher.py
    test_api.py              <- Route tests including auth rejection
  alembic/
    versions/
  .env.example
  alembic.ini
  pyproject.toml
  README.md
```

### Dependencies

| Package | Purpose |
|---|---|
| fastapi + uvicorn | API server |
| anthropic | Claude SDK |
| sqlalchemy + alembic | ORM + migrations |
| tweepy | Official X API client |
| twikit | Free X posting (dev/staging) |
| pyyaml | Config loading |
| pydantic | Validation (included with FastAPI) |
| psycopg2-binary | Postgres driver |
| pytest | Testing |

### What's intentionally NOT in Phase 1

- No threads — single tweets only. Thread support with partial-failure reconciliation is Phase 2.
- No Celery/Redis/APScheduler — all publishing is manual (user-triggered), no background jobs
- No frontend — API-only
- No Docker — run with uvicorn directly, Dockerize later
- No partner data triggers — standalone content generation only
- No analytics feedback loop — user picks from variants manually, not performance-optimized
- No autonomous scheduling — no cron, no cadence rules, no posting windows (Phase 2)
- No score threshold compliance check — no athlete data source to check against (Phase 5)
- No Twikit in production — dev/test only, official Tweepy publisher for live posting

---

## 8. Growth Path (Phases 2-11)

How Phase 1 modules expand into the full system:

| Phase | Adds | Where it goes |
|-------|------|---------------|
| 2 | Autonomous scheduling (cadence cron, posting windows, DB-locked jobs) + dashboard (React) | scheduler/ module, new frontend, API endpoints expand |
| 3 | LinkedIn publisher + approval UI | publishers/linkedin.py, approval tiers in compliance |
| 4 | Instagram publisher + Canva templates | publishers/instagram.py, assets/template_engine.py |
| 5 | Partner webhooks + event triggers | webhooks/ module, triggers/partner_events.py |
| 6 | Analytics agent | agents/analytics.py, feeds back into content_writer |
| 7 | Repurposing engine + sports calendar | agents/repurposer.py, data/sports_calendar.py |
| 8 | UGC pipeline | agents/ugc_intake.py |
| 9 | Blog/SEO generation | agents/blog_writer.py, CMS integration |
| 10 | Newsletter | agents/newsletter.py, ESP integration |
| 11 | Competitor Scout + Lead Nurture + Campaign Planner | agents/competitor_scout.py, agents/lead_nurture.py, agents/campaign_planner.py |

At full build, the system remains a modular monolith with ~15 modules sharing one Postgres database. Heavy workers (analytics, competitor monitoring) can be extracted to separate Railway services if needed for scale.
