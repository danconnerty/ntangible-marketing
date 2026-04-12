# Analytics Redesign

Replace the current boilerplate analytics page with real data-driven analytics built from internal publishing history and platform engagement metrics.

## Decision Summary

- **Data source**: Internal (DraftVariant, ReviewAction, AnalyticsSnapshot) + platform API metrics pulled via saved connections
- **Approach**: Pull historical data once on platform connect, sync metrics after each publish, serve from cache on page load
- **Charting**: Chart.js via CDN, line charts with metric/period dropdowns
- **No external engagement data required to start** — internal data (approval rates, publishing volume, content scores) works immediately; engagement metrics layer on when platforms are connected

## Page Layout

### Platform Tabs

Horizontal tabs at the top: **LinkedIn | X | Instagram | Newsletter**

Clicking a tab reloads the page filtered to that platform. Default to the first platform that has data (or LinkedIn if none).

### Summary Cards

Four cards below the tabs showing counts for the selected platform:

| Card | Source |
|---|---|
| Total Published | `DraftVariant` where `state=PUBLISHED` and `platform=selected` |
| Approval Rate | published / (published + rejected + expired) as % |
| Rejected | `DraftVariant` where `state=REJECTED` and `platform=selected` |
| Expired | `DraftVariant` where `state=EXPIRED` and `platform=selected` |

### Line Chart

A line chart with two dropdowns:

**Metric dropdown** (what to plot):
- Engagement Rate — average (likes + comments + shares) / impressions per time bucket. Only available when platform is connected and metrics have been synced.
- Impressions — total impressions per time bucket. Only available when connected.
- Publishing Volume — count of posts published per time bucket. Always available.
- Approval Rate — % of drafts approved per time bucket. Always available.
- Content Score — average internal content score (0-100) per time bucket. Always available.

**Period dropdown** (time range):
- 7 days (daily buckets)
- 30 days (daily buckets)
- 90 days (weekly buckets)

If the selected metric has no data (e.g. engagement rate with no connected platform), show "Connect your [platform] account on the Status page to see engagement data" with a link.

Chart rendered with Chart.js loaded from CDN. Backend provides the data as a JSON array of `{date, value}` objects embedded in the template.

### Post List

Two sub-tabs below the chart: **Published | Rejected**

**Published tab** — list of published posts for this platform, newest first:
- Content preview (first 150 characters)
- Published date and time
- Published via (manual / automatic / scheduled)
- Workflow name
- Engagement metrics if available (impressions, engagement rate) — otherwise "No metrics yet"

**Rejected tab** — list of rejected drafts for this platform, newest first:
- Content preview (first 150 characters)
- Rejected date and time
- Rejected by (actor name)
- Rejection reason (from ReviewAction notes)
- Workflow name

Both lists paginated at 20 items, with "Load more" button.

## Data Flow

### On platform connect (one-time historical pull)

1. User saves connection on Status page
2. Backend calls platform API to fetch post metrics from last 90 days
3. For each post found: create or update `AnalyticsSnapshot` with metrics (impressions, engagement_rate, likes, comments, shares)
4. This runs synchronously during the connect request (acceptable for one-time pull)

### After each publish

1. Post published via publisher, `platform_post_id` saved on `DraftVariant`
2. After successful publish, call platform API to pull initial metrics for that post
3. Store in `AnalyticsSnapshot`

### On analytics page load

1. Query `DraftVariant` filtered by `platform` param
2. Query `AnalyticsSnapshot` joined to drafts for engagement data
3. Query `ReviewAction` for rejection reasons
4. Aggregate into summary cards, chart data points, and post lists
5. No live API calls — all data served from database

### Metric refresh

When the analytics page loads and there are published posts with `AnalyticsSnapshot` data older than 1 hour within the last 7 days, refresh those metrics in the background. This keeps recent post metrics reasonably current without hammering the APIs.

## Platform API Calls

### LinkedIn
- `GET /organizationalEntityShareStatistics` — impressions, clicks, engagement, likes, comments, shares per post
- Uses the access token from `app_connections` where channel=linkedin

### X / Twitter
- `GET /2/tweets/:id` with `tweet.fields=public_metrics` — impressions, likes, retweets, replies, quotes
- Uses bearer token or OAuth from `app_connections` where channel=x

### Instagram
- `GET /{media-id}/insights` — impressions, reach, engagement, likes, comments, shares, saves
- Uses the access token from `app_connections` where channel=instagram

### Newsletter (Mailchimp)
- `GET /reports/{campaign_id}` — opens, clicks, bounces, unsubscribes
- Uses the API key from `app_connections` where channel=newsletter

## Code Changes

### New file: `app/services/platform_metrics_sync.py`

Handles pulling metrics from each platform API:
- `sync_historical_metrics(db, channel)` — called once on connect, pulls last 90 days
- `sync_post_metrics(db, draft_variant)` — called after publish, pulls metrics for one post
- `refresh_stale_metrics(db, channel, max_age_hours=1)` — refreshes recent posts with stale data
- Platform-specific helpers: `_pull_linkedin_metrics()`, `_pull_x_metrics()`, `_pull_instagram_metrics()`, `_pull_newsletter_metrics()`

### Modified: `app/web/templates/analytics.html`

Complete rewrite:
- Platform tabs (HTMX-powered, swap page content on click)
- Summary cards section
- Chart.js canvas with metric/period dropdowns
- Published/Rejected sub-tabs with post lists
- "Load more" pagination via HTMX

### Modified: `app/web/routes.py`

Update the `GET /control-room/analytics` route:
- Accept `platform` query param (default: linkedin)
- Accept `metric` and `period` query params for chart
- Accept `tab` query param (published/rejected) for post list
- Query DraftVariant, ReviewAction, AnalyticsSnapshot
- Build chart data as JSON array
- Return filtered summary, chart data, and post list

### Modified: `app/services/review_queue.py`

After successful publish in `publish_due_draft()`:
- Call `sync_post_metrics(db, draft_variant)` to pull initial metrics

### No schema changes

All needed tables exist: `AnalyticsSnapshot`, `PublicationRecord`, `DraftVariant`, `ReviewAction`.

## What Does NOT Change

- Database schema
- Scoring algorithm in `analytics_ingest.py`
- API routes (`/api/analytics/*`)
- Other pages (Dashboard, Activity, Workflows, Status)
