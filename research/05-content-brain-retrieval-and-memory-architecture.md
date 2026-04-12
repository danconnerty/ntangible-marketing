# Historical Content Retrieval and Content-Brain Architecture

## Research Question
How can NTangible retrieve and store its historical LinkedIn, X, Instagram, and newsletter content, along with engagement/performance data, so future content generation can use that history as a reliable "brain"?

## Key Findings

### LinkedIn organization posts, reactions, comments, and page analytics
- **Source:** LinkedIn Microsoft Learn and LinkedIn Help | **Trust:** Tier 1
- **What LinkedIn exposes:** The current Posts API allows retrieval of organization-authored posts. The Social Metadata API returns reaction and comment summaries, and the Social Actions APIs can retrieve detailed likes and comments. The Organization Page Statistics API returns lifetime and time-bounded page view and click statistics. LinkedIn Help also documents Page analytics exports from the admin UI.
- **Key technical details:**
  - Posts retrieval: organization posts are retrievable with `r_organization_social`, and the authenticated member must have an eligible Page role such as `ADMINISTRATOR`, `DIRECT_SPONSORED_CONTENT_POSTER`, or `CONTENT_ADMIN`.
  - Social metadata summary: `GET /rest/socialMetadata/{shareUrn|ugcPostUrn|commentUrn}` returns reaction summaries and comment counts.
  - Detailed likes/comments: `GET /rest/socialActions/{shareUrn|ugcPostUrn|commentUrn}/likes` and `/comments`.
  - Page analytics: `organizationPageStatistics` supports both lifetime and time-bounded views/clicks; LinkedIn Help also supports manual Page analytics export as XLS from the admin UI.
  - Newsletter/admin export: LinkedIn Help search results indicate Page admins can export analytics for Content, Visitors, Followers, Search Appearances, Leads, Newsletters, and Competitors from the analytics UI.
- **Important limits:** LinkedIn's Pages Data Portability API requires application review. LinkedIn also notes that members control whether Page owners can export some individual interaction/profile data, and privacy settings can remove some member-linked fields from exports.
- **Relevance to us:** LinkedIn can be a strong source of both raw post history and analytics, but access control is stricter than X or an email ESP. We should use both API and admin exports.
- **Code:** Official REST endpoints are documented by LinkedIn; no NTangible code exists yet.

### X provides two separate retrieval paths: API for metrics and archive for full history
- **Source:** X Developer Platform and X Help | **Trust:** Tier 1
- **What X exposes:** X API v2 supports post retrieval and per-post metrics. Public metrics include likes, replies, quotes, and reposts. Non-public and organic metrics for owned/authorized accounts include impressions and click metrics. X Help also documents the full account archive export, which starts from the first post and includes machine-readable HTML and JSON files.
- **Key technical details:**
  - Historical timeline access through the user post timeline is limited to the most recent 3,200 posts.
  - Tweet lookup supports `public_metrics`, `non_public_metrics`, `organic_metrics`, and `promoted_metrics`.
  - X Help says the account archive includes posts, media, followers, following, ads seen/engaged with, and more, starting with the first post.
  - The X Ads API supports campaign analytics and longer-window async reporting for paid/promoted activity.
- **Important limits and contradictions:**
  - As of April 6, 2026, the public X documentation has partly shifted to a pay-per-use framing on `docs.x.com`, while older developer pages and support docs still reference Free/Basic/Pro style tiering and historical volume limits. This means pricing and read caps should be verified in the live developer console during implementation.
  - The API timeline will not give us every historical post if the account has posted more than 3,200 times. The archive is required for full text/media history.
  - The archive is the safest way to get complete historical post bodies, but performance metrics must still come from API reads or from prior internal analytics snapshots.
- **Relevance to us:** For X, the right backfill is archive first, API second. Archive gives us completeness; API gives us richer metrics for the posts we can still query.
- **Code:** Official X API and Help documentation; no NTangible code exists yet.

### Instagram history is possible, but only under professional-account constraints
- **Source:** Meta/Facebook Help Center and Instagram Help Center | **Trust:** Tier 1
- **What Meta exposes:** Professional Instagram accounts can be connected to a Facebook Page to access cross-app tools and third-party app integrations. Meta Help documents account/content insights for professional accounts, data export from Accounts Center, and important retention constraints for insights.
- **Key technical details:**
  - You need a business or creator account to view Instagram Insights.
  - You can only see insights for content posted since the account converted to a business or creator account.
  - Meta Help says if an account switches back to personal, access to insights is lost, though insight data is preserved for 90 days if the account switches back to business/creator within that window.
  - Instagram data can be exported from Accounts Center, including date-range exports and machine-readable files.
  - Connecting a professional Instagram account to a Facebook Page enables third-party app integrations.
- **Inference from sources:** The standard programmatic retrieval path is the Instagram Graph API tied to the professional account/Page connection. The Help sources do not spell out the API endpoints directly, but they do confirm the professional-account and Page-linkage prerequisites that make API access possible.
- **Important limits:** Instagram is the weakest channel for guaranteed all-time analytics recovery. If NTangible's Instagram account became professional recently, earlier posts may exist in the archive but not have API-grade insight history. The 90-day language in Meta Help is especially important for account-level insight visibility.
- **Relevance to us:** Instagram requires the most defensive backfill plan: export raw data, use Meta business/professional tooling, and accept that some older metrics may be irrecoverable if they were never captured after professional conversion.
- **Code:** No NTangible code exists yet.

### LinkedIn newsletters are retrievable differently from email newsletters
- **Source:** LinkedIn Help | **Trust:** Tier 1
- **What LinkedIn exposes:** LinkedIn newsletters have dedicated newsletter pages, subscriber analytics, article views, and admin analytics surfaces. LinkedIn Help states that newsletter authors can access newsletter analytics, including article views and new subscribers, over date ranges up to the past 365 days.
- **Key technical details:**
  - A LinkedIn Page newsletter is separate from the LinkedIn Page itself.
  - Newsletter analytics include article views and new subscribers; LinkedIn search results also indicate newsletter analytics can be exported from the Page analytics UI.
- **Important limits:** LinkedIn newsletter data and email newsletter data should not be mixed together. They are separate content systems and should be modeled separately in the content brain.
- **Relevance to us:** If NTangible has both LinkedIn newsletters and an external email newsletter, both should be ingested, but as different content sources.
- **Code:** N/A

### Mailchimp has strong API coverage for newsletter backfill and reporting
- **Source:** Mailchimp Developer and Mailchimp Help | **Trust:** Tier 1
- **What Mailchimp exposes:** The Marketing API exposes campaign listing and reporting endpoints. Reports are read-only and include opens, clicks, abuse, and additional report detail endpoints.
- **Key technical details:**
  - `GET /campaigns` lists campaigns.
  - `GET /reports` and `GET /reports/{campaign_id}` return sent-campaign report data.
  - Click-level and open-level report endpoints are also documented.
  - Account exports are available through the API as well.
- **Relevance to us:** If NTangible used Mailchimp, this is the cleanest newsletter backfill path: campaigns for content, reports for performance.
- **Code:** Official API reference only.

### Kit (formerly ConvertKit) also supports a usable newsletter backfill path
- **Source:** Kit Developer Documentation and Kit Help Center | **Trust:** Tier 1
- **What Kit exposes:** Kit's API exposes broadcasts, broadcast stats, and broadcast click details. Kit Help also documents reporting and CSV exports for subscriber chart data.
- **Key technical details:**
  - `GET /v4/broadcasts` lists broadcasts.
  - `GET /v4/broadcasts/{id}` retrieves a broadcast.
  - `GET /v4/broadcasts/{broadcast_id}/stats` returns recipients, open rate, emails opened, click rate, unsubscribe rate, unsubscribes, total clicks, status, and send progress.
  - `GET /v4/broadcasts/{broadcast_id}/clicks` returns link click detail.
  - Kit Help says broadcast reports show content, recipients, opens, clicks, and more.
- **Important limits:** Kit Help notes they no longer update email data for broadcasts sent before August 1, 2023, even though historical tracking remains visible.
- **Relevance to us:** If NTangible used Kit/ConvertKit, it is fully viable as a newsletter-memory source, but older broadcast metrics may have update caveats.
- **Code:** Official API reference only.

## Synthesis
The answer is yes, but not with a single source.

To build a real NTangible content brain, we should retrieve data from four source categories:

1. **Official platform APIs** for structured, queryable post data and metrics.
2. **Native platform/admin exports** for one-time historical backfills and edge cases.
3. **Account archives** where APIs are incomplete, especially X and Instagram.
4. **Internal marketing systems** such as Mailchimp/Kit, scheduler exports, CRM notes, and drive folders if they exist.

### What I am confident we can recover
- The raw text/media history of X posts, using the X archive.
- Recent X post metrics, using X API lookup/timeline calls.
- LinkedIn Page post history plus reactions/comments summaries and Page analytics, assuming Page admin access.
- LinkedIn newsletter editions and newsletter analytics, if NTangible used LinkedIn newsletters.
- Email newsletter send history and performance, if NTangible used a standard ESP such as Mailchimp or Kit.
- Instagram raw content history via export, plus professional-account insights for content posted after conversion to business/creator.

### What I am not willing to overclaim
- I am **not** 100% confident we can recover every historical Instagram metric ever posted if the account was not a professional account at the time or if insights were never captured.
- I am **not** 100% confident X pricing/read limits documented on older support pages still exactly match the live April 2026 billing model, because X's docs now show a pay-per-use framing and older tier docs still surface in search.
- I am **not** 100% confident LinkedIn will expose all member-level interaction details without portability review and user privacy allowances.

### Recommended retrieval plan
1. **Account inventory**
   - List every NTangible-controlled surface:
   - LinkedIn Page(s)
   - LinkedIn newsletter(s)
   - X account(s)
   - Instagram professional account(s)
   - Email ESP account(s)
   - Any scheduler used before now

2. **One-time backfill**
   - LinkedIn: export Page analytics XLS and pull Page posts via API.
   - X: request full X archive, then enrich the most recent queryable posts through X API metrics.
   - Instagram: export from Accounts Center, then enrich with professional insights where available.
   - Mailchimp/Kit: pull campaigns/broadcasts plus reports/stats.

3. **Ongoing sync**
   - Nightly API sync for all channels.
   - Weekly performance snapshot table so we do not lose time-series metrics when platforms change retention or reporting windows.

4. **Storage model**
   - `content_items`
   - `content_metrics_snapshots`
   - `content_assets`
   - `content_tags`
   - `content_sources`
   - `newsletter_campaigns`
   - `generation_log`
   - `content_embeddings`

5. **Retrieval model for the writer agent**
   - SQL filters for hard constraints: platform, date range, audience, post type, intent, top performers.
   - Vector search for semantic similarity: "find winning posts that feel like this angle."
   - Hybrid retrieval before generation:
   - pull top-performing similar posts
   - pull recent posts to avoid repetition
   - pull audience-specific winners
   - inject compact summaries, not raw dumps

### Practical conclusion
The "brain" should not be a folder full of screenshots or copied captions.

It should be:
- a **historical warehouse** of NTangible content and metrics,
- plus a **search layer** for retrieval,
- plus a **snapshot layer** that preserves metrics over time,
- plus a **generation interface** that feeds the best historical context into the writer.

That architecture is feasible with the official sources above, but the exact completeness of the backfill will depend on:
- whether NTangible still has admin access to every account,
- whether Instagram has always been a professional account,
- whether there was a prior ESP or scheduler,
- and whether any older metrics were never available through official surfaces.

## Relevance
HIGH

## METHODOLOGY.md Update
No `METHODOLOGY.md` file exists in this repo. If one is added later, include: "Backfill historical content using official APIs + admin exports + account archives, then preserve time-series metrics locally with scheduled snapshots."
