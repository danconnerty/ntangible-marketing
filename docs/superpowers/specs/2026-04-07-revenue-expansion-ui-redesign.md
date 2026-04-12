# Revenue & Expansion Page UI/UX Redesign

**Date:** 2026-04-07
**Status:** Approved
**Scope:** Template and CSS changes to `/control-room/revenue` and `/control-room/expansion`

## Problem

Both pages lack strategic context. An operator visiting them doesn't understand what they're for or why they matter. The Revenue page lists playbooks, goals, and packages without explaining their commercial purpose. The Expansion page is a flat grid of module cards with generic one-line descriptions. Neither page connects back to the blueprint's strategic goals.

## Design Direction

Hybrid approach: strategic mission header with KPI metric cards at top, then blueprint-sourced descriptions baked into each card/section below. Follows the pattern established by the Analytics page.

---

## Revenue Page (`/control-room/revenue`)

### Page Header

- **Eyebrow:** "Revenue Engine" (green accent, `--revenue-green: #059669`)
- **Title:** "Close Deals. Warm Leads. Arm Partners."
- **Subtitle:** "Every piece of content should either close a deal, warm a lead, or arm a partner to sell on NTangible's behalf. Revenue-tagged content should represent 25-30% of posting volume. This page tracks what drives pipeline, not just what gets likes."

Source: Blueprint Section 7 intro + Section 7.4

### KPI Metric Cards (4-column grid)

| Card | Label | Value Source | Hint |
|------|-------|-------------|------|
| 1 (highlight, green left border) | Active Playbooks | Count of `playbooks` where `active=true` | "Ready to execute" |
| 2 | Executions (30d) | Count of `executions` | "Across all playbooks" |
| 3 | Conversion Goals | Count of `conversion_goals` | "{active} active, {inactive} pending" |
| 4 | Sales Packages | Count of `sales_packages` | "{delivered} delivered, {review} pending review" |

### Revenue Playbooks Section

- **Section header:** "Revenue Playbooks"
- **Section description:** "Pre-built sales motions that generate conversion-focused content. Each playbook targets a specific buyer persona with proof-led messaging and an explicit CTA."
- **Card layout:** Grid, `repeat(auto-fill, minmax(290px, 1fr))`
- **Each playbook card contains:**
  - Playbook name (bold, 15px)
  - Badges: `playbook_type` (green badge) + `persona` (purple badge) + optional `inactive` (muted)
  - **Purpose block** (new): Blueprint-sourced strategic description in a left-bordered quote style. Mapped by playbook slug:
    - `alliance-registration-push`: "Drives assessment sign-ups during July/Aug and December testing windows. Urgency-driven messaging tied to real platform data: 'Coaches from D1 programs searched Clutch Factor scores this week.'" (Source: Section 7.2)
    - `fss-roi-summary`: "Packages hard ROI numbers FSS can use with their board: athletes tested, profiles viewed by coaches, commitment rates. Proves the integration's value after each event circuit." (Source: Section 7.2)
    - `coach-demo-push`: "Makes other programs ask 'why don't we have this?' Short-form case studies from verified clients designed to drive demo requests from coaches and front offices." (Source: Section 7.3)
    - Default (unknown slugs): No purpose block shown
  - Offer and CTA fields (as today)
  - Run Playbook button (green: `--revenue-green`)

### Conversion Goals Section

- **Section description:** "Track what actually moves pipeline. Revenue-tagged posts are tracked separately for conversion metrics — link clicks, demo requests, DMs — so the engine optimizes for what drives revenue, not just engagement." (Source: Section 7.4)
- **Goal rows** now show:
  - Goal name (bold)
  - Metric type + attribution window in a meta line below the name
  - Active/inactive badge

### Sales Enablement Section

- **Section description:** "Content bundles delivered to partner marketing teams. Partners like Alliance and FSS don't just need social content — they need sales ammunition. These packages arm them with conversion-focused material tailored to their sales motion." (Source: Section 7.2)
- **Enablement rows** now show:
  - Headline (bold)
  - Detail line: `package_kind` + source playbook
  - Status badge (needs_review = warning amber, delivered = success green)

### Recent Executions Section

- **Section description:** "History of playbook runs and their outcomes."
- Table layout: Playbook (name + type), Source, Status badge

### Visual Identity

- Revenue-specific green accent: `--revenue-green: #059669`, `--revenue-green-light: rgba(5, 150, 105, 0.08)`
- Run Playbook buttons use `.btn-revenue` (green background)
- Highlight metric card gets green left border
- Type badges use green tint

---

## Expansion Page (`/control-room/expansion`)

### Page Header

- **Eyebrow:** "Content Expansion" (purple accent, `--expansion-purple: #7c3aed`)
- **Title:** "One Proof Point, Many Formats"
- **Subtitle:** "Social is rented land — one algorithm change and reach drops to zero. These six modules turn every piece of content into 5-10 derivative pieces across formats and platforms, while building owned assets that survive algorithm shifts."

Source: Blueprint Section 11.2 intro + Section 11.8

### KPI Metric Cards (3-column grid)

| Card | Label | Value Source | Hint |
|------|-------|-------------|------|
| 1 (highlight, purple left border) | Active Modules | Hardcoded 6 (or count of modules list) | Module names listed |
| 2 | Total Assets | Sum of all module counts | "Across all expansion lanes" |
| 3 | Derivatives Created | Count from repurposing `derivatives` | "From {sources} source pieces" |

### Module Grid (2-column)

Each module card contains:

- **Icon** (color-coded SVG per module):
  - Blog: blue (`--info`)
  - Science: purple (`--expansion-purple`)
  - Video: pink (`#e1306c`)
  - UGC: green (`--success`)
  - Repurposing: amber (`--warning`)
  - Sports: dark (`--text`)
- **Title + count** (e.g., "Blog & SEO" / "4 articles")
- **Blueprint section badge** (e.g., "Section 11.2")
- **Purpose block** (left-bordered quote): Blueprint-sourced strategic description per module:
  - **Blog:** "Own the search results. When a D1 coach googles 'mental performance assessment for athletes' or 'clutch factor testing,' NTangible should own that result. 2-4 SEO-optimized posts per month, 800-1,200 words each." (Section 11.2)
  - **Science:** "Proactive defense, not reactive. Competitors like Scorability ($40M raised) occupy mindshare. Advisor spotlights, white paper excerpts, and dataset credibility posts establish validated methodology before credibility is challenged." (Section 11.1)
  - **Video:** "~10% of content volume. High-impact moments only — partnership announcements, conference recaps, milestone celebrations. The engine generates the script (hook, talking points, CTA); Dan records. No editing required beyond basic trim." (Section 11.4)
  - **UGC:** "The most powerful version isn't NTangible posting about athletes — it's athletes posting about themselves. Athletes scoring 750+ CF get automated testimonial requests. One submission creates 3-5 content pieces at zero production cost." (Section 11.5)
  - **Repurposing:** "The highest-leverage move in the system. One content nucleus (e.g., a LinkedIn post) automatically becomes an X thread, single tweet, IG caption, blog expansion, newsletter excerpt, and email snippet. Posts scoring 75+ are auto-queued. Dan's input gets amplified 5-10x without additional effort." (Section 11.8)
  - **Sports:** "The sports calendar drives everything. Content not mapped to the calendar feels disconnected. Pre-loaded macro windows — combine season, transfer portal, draft week, testing windows — auto-stage content templates so the engine is ready when moments hit." (Section 11.6)
- **Status stats row** (mono font, top-bordered): Module-specific breakdowns
  - Blog: Draft / Published / Scheduled
  - Science: Spotlights / Excerpts
  - Video: Scripted / Recorded
  - UGC: Sent / Received / Published
  - Repurposing: Sources / Derivatives / Ratio (derivatives/sources)
  - Sports: Active / Upcoming / Completed
- **Open button** linking to module page

### Visual Identity

- Expansion-specific purple accent: `--expansion-purple: #7c3aed`, `--expansion-purple-light: rgba(124, 58, 237, 0.08)`
- Eyebrow and highlight border use purple
- Section badges use purple tint

---

## CSS Changes

New CSS rules added to `control_room.css`:

1. **Revenue green variables** and `.btn-revenue` button class
2. **Expansion purple variables** (already partially exist as trigger-calendar purple)
3. **Eyebrow class** for page header label: `.page-header .eyebrow` — 11px, 700 weight, uppercase, 0.08em letter-spacing
4. **Purpose block** class: `.purpose-block` — 13px, muted color, left 2px border, 10px left padding
5. **Module card** styles: `.module-card`, `.module-top`, `.module-icon`, `.module-title-block`, `.module-stats`
6. **Metric highlight** variant: `.metric-card.highlight-revenue` (green border), `.metric-card.highlight-expansion` (purple border)
7. **Goal meta** line: `.goal-meta` for metric type + attribution window

## Template Changes

### `expansion.html`

Complete rewrite. New structure:
1. Page header with eyebrow/title/subtitle
2. 3-column metric grid
3. 2-column module grid with enriched cards

### `revenue.html`

Complete rewrite. New structure:
1. Page header with eyebrow/title/subtitle
2. 4-column metric grid
3. Playbook grid with purpose blocks
4. Conversion goals with metric details
5. Sales enablement with richer rows
6. Recent executions table

## Backend Changes

### `load_expansion_modules()` in `app/web/routes.py`

Add to each module dict:
- `icon`: slug used for CSS class (already matches slug)
- `section_ref`: blueprint section reference string
- `purpose`: blueprint-sourced description string
- `stats`: dict of module-specific status breakdowns (pulled from existing service dashboard data)

Stat breakdowns by module:
- **Blog:** `{"draft": count, "published": count, "scheduled": count}` — derive from `blog.get("counts", {})`
- **Science:** `{"spotlights": count, "excerpts": count}` — derive from `science.get("counts", {})`
- **Video:** `{"scripted": count, "recorded": count}` — derive from `video.get("count", 0)`, recorded defaults to 0
- **UGC:** `{"sent": request_count, "received": submission_count, "published": published_count}` — derive from existing ugc dashboard
- **Repurposing:** `{"sources": len(sources), "derivatives": len(derivatives), "ratio": ratio}` — derive from existing repurposing dashboard
- **Sports:** `{"active": count, "upcoming": count, "completed": count}` — derive from existing sports dashboard windows

### `revenue_view()` in `app/web/routes.py`

Add computed summary values to template context:
- `active_playbook_count`: count of playbooks where active=true
- `execution_count`: len of executions list
- `active_goal_count`: count of goals where active=true
- `inactive_goal_count`: count of goals where active=false
- `delivered_package_count`: count of packages with status "delivered"
- `review_package_count`: count of packages with status "needs_review"

### `_serialize_goal()` in `app/services/revenue_service.py`

Add `attribution_window_days` to the serialized goal dict (currently missing — the model has the field but the serializer omits it).

### Playbook purpose mapping

A dict in the view function mapping playbook slugs to blueprint-sourced purpose strings. Added to each playbook dict as `purpose` before passing to template. Unknown slugs get no purpose block.

## No New Dependencies

All changes use existing CSS custom properties, Jinja2 templating, and data already returned by services. No new packages, no new API endpoints, no new database queries.

## Testing

- Existing `test_web_revenue_view.py` and `test_web_expansion_view.py` continue to pass (template rendering)
- Verify new template elements render with mock data
- Verify metric calculations are correct with edge cases (empty lists, all inactive, zero derivatives)
