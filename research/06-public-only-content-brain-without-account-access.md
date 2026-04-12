# Public-Only NTangible Content Brain Without Account Access

## Research Question
How can someone who does **not** have access to NTangible's social or newsletter accounts build a useful historical content database anyway, using only public data and legally/technically available third-party retrieval paths?

## Key Findings

### X is the strongest public-only source
- **Source:** X Help and X Developer Platform | **Trust:** Tier 1
- **What X exposes publicly:** X says public posts are visible to anyone, whether or not they have an X account. X also says its user Post timeline API supports OAuth 2.0 App-Only for public timelines, and Tweet lookup returns `public_metrics`.
- **Key technical details:**
  - Public posts are visible to anyone: X Help says public posts are visible on or off X.
  - Public timeline retrieval: the v2 user Post timeline supports OAuth 2.0 App-Only and provides access to the most recent 3,200 posts.
  - Public metrics: Tweet lookup can return `public_metrics` such as likes, replies, quotes, and reposts.
  - Public web limit: X Help says profile tabs can be truncated in the web UI, with only 800 posts in the Posts tab and 3,200 in Posts & Replies.
- **Relevance to us:** Even without NTangible login or API tokens from NTangible, you can still collect a strong public history of X posts plus basic engagement counts. If you have your own X developer app, you can do this more cleanly through the API.
- **Code:** Official docs only.

### LinkedIn has no official public read path for third-party organization post history
- **Source:** LinkedIn Microsoft Learn and LinkedIn Help | **Trust:** Tier 1
- **What LinkedIn exposes:** LinkedIn's Posts API and Social Actions API both require `r_organization_social` for organization posts, and that permission is restricted to authenticated members with eligible Page roles. LinkedIn Page analytics export is also admin-only.
- **Key technical details:**
  - Posts API: retrieving organization-authored posts requires `r_organization_social` and Page role access.
  - Social Actions API: retrieving comments and likes for organization content also requires `r_organization_social`.
  - Page analytics export: LinkedIn Help says exporting content, followers, visitors, newsletters, competitors, and related analytics requires Page admin access.
  - Public visibility still exists: LinkedIn Help says posts with visibility set to `Anyone` can be visible off LinkedIn, and public profiles can appear in public search engines. LinkedIn also says newsletter pages can be viewed without login.
- **Relevance to us:** Without NTangible admin access, there is no official API route for comprehensive LinkedIn backfill. The only viable route is public web collection of what LinkedIn exposes off-platform or on public newsletter/profile pages.
- **Code:** Official docs only.

### LinkedIn newsletters are one of the best no-access LinkedIn targets
- **Source:** LinkedIn Help | **Trust:** Tier 1
- **What LinkedIn exposes publicly:** LinkedIn Help states that newsletter pages can be viewed without signing in, and those pages show past editions.
- **Key technical details:**
  - Newsletter pages are separate from the LinkedIn Page itself.
  - Anyone can visit a newsletter page without logging in.
  - Past editions are visible from the newsletter page.
- **Relevance to us:** If NTangible used LinkedIn newsletters, those public newsletter pages are a much better no-access target than normal LinkedIn Page posts.
- **Code:** N/A

### Instagram is mixed: public web is easy, official API access is conditional
- **Source:** Instagram/Facebook Help Center and Meta docs references | **Trust:** Tier 1 with one documented inference
- **What Meta exposes publicly:** Instagram says professional accounts are public, public posts/profiles can be embedded, and profile information such as follower/following counts and bio are public. Instagram also says insights are only for business/creator accounts and only for content posted after conversion.
- **Key technical details from official Help:**
  - Public profile info includes username, bio, links, follower count, and following count.
  - Public posts and profiles can be embedded if the account is public and embeds are enabled.
  - Insights are only available for business or creator accounts.
  - You can only see insights for content posted since converting to business/creator.
- **Important inference:** Meta's official Instagram API documentation includes a Business Discovery guide/reference for querying public professional accounts. I was able to verify the official docs URL from search results but not fetch the page directly in this browser. Based on the official Help prerequisites and the official docs URL pattern, this appears to be the official programmatic path for third-party reads of public business/creator accounts.
- **Relevance to us:** Even without NTangible account access, Instagram can still be mined from public profile pages, embeds, public follower/post counts, and public post URLs. If NTangible's account is a public business/creator account, Business Discovery is likely the best official API path to verify during implementation.
- **Code:** Official Help pages; Business Discovery doc URL should be verified directly during implementation.

### Public email newsletter archives are feasible if the sender made them public
- **Source:** Mailchimp Help and Kit Help | **Trust:** Tier 1
- **What Mailchimp exposes publicly:** Mailchimp says every sent campaign has a browser-based campaign page, and each audience can have a public archive page containing the most recent campaigns, unless the owner hides or restricts it.
- **What Kit exposes publicly:** Kit says broadcasts can have public links, can be published to the web, and can appear in a public newsletter feed on the creator profile.
- **Key technical details:**
  - Mailchimp creates campaign pages and an archive page of recent campaigns.
  - Mailchimp archive pages can be hidden or filtered by the owner.
  - Kit broadcasts can have either a public link or an archive link.
  - Kit broadcasts can be published to the web and shown in a public newsletter feed.
- **Relevance to us:** If NTangible's newsletters were sent through Mailchimp or Kit and left public, you can reconstruct a meaningful newsletter history without any account access at all.
- **Code:** Official Help docs only.

### Web archives are the best fallback for public-only history
- **Source:** Internet Archive Help Center | **Trust:** Tier 1
- **What the Wayback Machine exposes:** The Internet Archive says you can use the Wayback Machine to preserve and revisit public web pages, and `Save Page Now` can create permanent URLs for specific public pages.
- **Key technical details:**
  - Saved pages keep a permanent archived URL.
  - `Save Page Now` works for most pages but not all; some sites block crawling.
  - It saves the page you enter, including images and CSS, but not an entire site crawl.
- **Relevance to us:** Without direct account access, the Wayback Machine is critical for recovering older public post pages, public newsletter pages, and website pages that have changed or disappeared.
- **Code:** Official Internet Archive docs only.

## Synthesis
Without NTangible account access, you can still build a **public-content brain**, but not a **full analytics brain**.

### What you can build confidently
You can build a database of:
- public X posts
- public X engagement counts
- public Instagram captions/profile stats/post URLs
- public LinkedIn newsletter editions
- some public LinkedIn posts if they are visible off LinkedIn or indexed
- public email newsletter pages if the ESP archive is public
- historical snapshots from the Wayback Machine

That is enough to learn:
- tone
- topics
- recurring hooks
- posting cadence
- format patterns
- audience angle
- repeated claims
- visible social proof

### What you cannot recover without cooperation
You should assume the following are **not recoverable** without NTangible access:
- LinkedIn impressions, clicks, visitor analytics, follower analytics history
- LinkedIn Page exports
- X private/organic metrics such as impressions and profile clicks if you cannot use owned-account auth
- Instagram insights such as reach, accounts engaged, profile visits
- newsletter opens, click rates, unsubscribe rates
- internal campaign tags, draft history, or CRM outcomes

### Best public-only collection strategy
1. **X**
   - Use public profile/timeline pages to discover post URLs.
   - Use your own X developer app to query public timelines and Tweet lookup where possible.
   - Store `text`, `created_at`, `conversation_id`, `public_metrics`, media refs, and permalink.

2. **Instagram**
   - Collect public profile pages and public post/reel URLs.
   - Store caption, media type, timestamp, permalink, visible like/comment counts if exposed, follower count snapshots, and profile bio/link snapshots.
   - If the account is a public business/creator account, verify Business Discovery during implementation and use it if available.

3. **LinkedIn**
   - Target public newsletter pages first.
   - Use public search results and public profile/activity visibility where available.
   - Treat LinkedIn Page posts as incomplete unless visible publicly on the web.
   - Do not assume full coverage is possible.

4. **Newsletters**
   - Search for Mailchimp campaign archives, Kit creator-profile newsletter feeds, website-hosted browser-view versions, and public "view in browser" links.
   - Store subject, publish date, body content, CTA, and public URL.

5. **Archives**
   - For every discovered public URL, check the Wayback Machine.
   - Save important pages to Wayback going forward.

### Storage model for a public-only brain
- `public_content_items`
- `public_content_metrics_observed`
- `public_content_assets`
- `public_source_urls`
- `public_archive_snapshots`
- `public_embeddings`

Recommended fields in `public_content_items`:
- `source_platform`
- `canonical_url`
- `author_handle`
- `published_at`
- `content_text`
- `content_type`
- `visible_like_count`
- `visible_comment_count`
- `visible_share_or_repost_count`
- `visible_follower_count_snapshot`
- `capture_method` (`api`, `public_web`, `newsletter_archive`, `wayback`)
- `captured_at`

### Retrieval model
The writer should retrieve:
- similar historical posts by topic/angle
- highest visible-engagement posts by platform
- recent posts to avoid repetition
- posts with the same audience or claim pattern

This gives you a useful creative memory even without private analytics.

### Hard truth
If you do not have NTangible access, the result will be:
- **good for style memory and topic memory**
- **okay for public-engagement heuristics**
- **bad for true performance optimization**

That is the real boundary.

## Relevance
HIGH

## METHODOLOGY.md Update
No `METHODOLOGY.md` exists in this repo. If one is added later, include: "When account access is unavailable, build a public-only content brain from public posts, public archives, public newsletter pages, and observed engagement snapshots; do not assume private analytics are recoverable."
