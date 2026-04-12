# NTangible Public Surface Inventory

## Research Question
Using only the information available in this workspace plus public web sources, what NTangible public URLs, handles, and public content surfaces can be identified for a public-only content-brain backfill?

## Key Findings

### Primary website and app structure
- **Source:** live site HTML and JavaScript bundle | **Trust:** Tier 1
- **What was found:** NTangible's main public domain is `https://ntangible.co/`. The site is a client-rendered React SPA served from Netlify. There is no public `sitemap.xml` or `robots.txt` at standard locations.
- **Key URLs:**
  - Website: `https://ntangible.co/`
  - Portal login: `https://portal.ntangible.co/login/`
- **Important implementation note:** The site bundle contains the current route map. Direct `curl` requests to some app routes return `404`, so route discovery should come from the JS bundle or a real browser session, not from assuming server-side route support.
- **Relevance to us:** The website itself is a public data source, but the collector must handle SPA behavior.

### Confirmed public social links embedded in the live site
- **Source:** live JS bundle | **Trust:** Tier 1
- **What was found:** The site's footer hardcodes three public social links and one portal link.
- **Confirmed links:**
  - Instagram: `https://www.instagram.com/ntangiblesports`
  - LinkedIn company page: `https://www.linkedin.com/company/ntangible/`
  - YouTube channel: `https://www.youtube.com/channel/UC6k2GMbwnIGyEOzXKPZZpWQ`
  - Calendly booking page: `https://calendly.com/ntangible/30min`
  - Portal login: `https://portal.ntangible.co/login/`
- **Relevance to us:** These are hard-confirmed public surfaces directly from the company's own live site.

### Instagram is live and public
- **Source:** Instagram public page response | **Trust:** Tier 1
- **What was found:** The public Instagram profile resolves and exposes open-graph metadata.
- **Verified metadata observed on April 6, 2026:**
  - Handle: `@ntangiblesports`
  - Followers: `908`
  - Following: `241`
  - Posts: `140`
- **Relevance to us:** Instagram is a strong public-only source with a verified handle and visible top-level profile counts.

### YouTube channel is live and exposes a handle
- **Source:** YouTube public page response | **Trust:** Tier 1
- **What was found:** The linked YouTube channel resolves and exposes both a title and canonical handle information.
- **Verified metadata observed on April 6, 2026:**
  - Channel title: `NTANGIBLE - YouTube`
  - Canonical handle: `@NTANGIBLE`
- **Relevance to us:** The channel is confirmed and can be collected without any account access.

### The YouTube RSS feed exposes a structured video history
- **Source:** YouTube public RSS feed and public oEmbed | **Trust:** Tier 1
- **What was found:** The NTANGIBLE channel has a public RSS feed that exposes machine-readable titles, published dates, video IDs, and visible view counts for recent uploads.
- **Feed URL:**
  - `https://www.youtube.com/feeds/videos.xml?channel_id=UC6k2GMbwnIGyEOzXKPZZpWQ`
- **Confirmed examples from the feed:**
  - `YzMUWlgYEcw` — `NTangible - General Information` — published `2026-02-01` — visible views `4`
  - `utbJt-G6ZIs` — `NTangible - NTerpret Announcement` — published `2025-11-18` — visible views `12`
  - `rtlmSfqJNdU` — `NTangible - Softball Testimonial (College Commitment)` — published `2025-11-08` — visible views `8`
  - `0Rus2IxRBsI` — `Using NTangible - Mental Development Tracking` — published `2025-08-26` — visible views `11`
  - `2uKgmDI9PR0` — `Using NTangible - Talent Identification` — published `2025-08-26` — visible views `3`
  - `MDkzosEhB_s` — `Using NTangible - Current Roster Score Alignment` — published `2025-08-26` — visible views `3`
  - `dVkUUqFcdus` — `Using NTangible - Current Roster Lineup Creation` — published `2025-08-26` — visible views `6`
  - `xDKOes-RC88` — `What is NTelligence?` — published `2025-08-26` — visible views `8`
  - `NvGbdlyVN3k` — `What is NSights?` — published `2025-08-26` — visible views `8`
  - `x1FuoojNCV0` — `What Do Clutch Factor™ Scores Mean?` — published `2025-08-26` — visible views `16`
  - `710Tiqy8ri0` — `What is the NTangible Assessment` — published `2025-08-26` — visible views `76`
  - `9S79ZbvIgog` — `NTangible - Typography Promo` — published `2025-07-14` — visible views `4`
- **Relevance to us:** The RSS feed is a better collection target than manual channel scraping because it already exposes normalized metadata for recent public video content.

### Public website route inventory is embedded in the app bundle
- **Source:** live JS bundle | **Trust:** Tier 1
- **What was found:** The current SPA bundle exposes the route map for major public pages.
- **Current public routes found:**
  - `/platform`
  - `/coaches`
  - `/recruiters`
  - `/directors`
  - `/team`
  - `/research`
  - `/partners`
  - `/testimonials`
  - `/contact`
  - `/alliance`
  - `/fss`
  - `/cfs`
  - `/mentalapproach`
  - `/privacy`
  - `/terms`
  - pricing/sales pages such as `/ncaa-pricing`, `/ncaa-direct`, `/propricing`, `/pro-direct`, `/smallcollegepricing`, `/small-college-direct`, `/preppricing`, `/prep-direct`, `/governorschallengepricing`
  - additional sales/demo routes such as `/football-sales`, `/basketball-sales`, `/sales-agreement-ncaa`, `/sales-agreement-youth`
- **Relevance to us:** Even if these routes do not resolve directly via plain HTTP fetch, they are valid public client-side routes and their bundles can still be collected.

### Contact and booking surfaces are public
- **Source:** contact-page bundle and live JS bundle | **Trust:** Tier 1
- **What was found:** The contact experience exposes a direct support email and an embedded Calendly demo flow.
- **Confirmed items:**
  - Support email: `support@ntangible.co`
  - Calendly booking URL: `https://calendly.com/ntangible/30min`
- **Important implementation note:** The contact page submits through `formsubmit.co` to `support@ntangible.co`, which confirms the email address as a real public-facing support endpoint.
- **Relevance to us:** These are useful metadata fields for the content brain and also confirm a lead-capture workflow on the public site.

### The research page exposes four public Google Drive papers
- **Source:** `Research-NxzUk_U8.js` bundle | **Trust:** Tier 1
- **What was found:** The public research page contains four specific public paper links and dates:
  - `The Science of Dyadic Congruence: Quantifying Coach-Player Alignment as a Determinant of Elite Performance`
    - Date: `February 4, 2026`
    - URL: `https://drive.google.com/file/d/17LjW7fip5Jw91lmeKc89mF5yu3__kNB5/view?usp=sharing`
  - `Individualized Pressure Profiling in Elite Sports`
    - Date: `December 9, 2025`
    - URL: `https://drive.google.com/file/d/1-nWGVn9teBVuhYqiKqhdNFdMvEt56MuU/view?usp=sharing`
  - `Inter-Rater Reliability Analysis of Assessment AI Scoring Method`
    - Date: `September 15, 2025`
    - URL: `https://drive.google.com/file/d/10fG01vUGZ8TOzHAijbq9F--NhTiobksb/view?usp=sharing`
  - `Predictive Findings of Clutch Performance in Collegiate Baseball`
    - Date: `September 15, 2025`
    - URL: `https://drive.google.com/file/d/1_LeTkmSa1edhFzmg6IhtUoLsiEJdKrPP/view?usp=sharing`
- **Relevance to us:** These are public, dated, content-rich artifacts that should be included in the content brain as part of NTangible's owned media and credibility content.

### Public leaderboards exist under the NTangible site/app
- **Source:** live JS bundle | **Trust:** Tier 1
- **What was found:** The public route map contains leaderboard routes, backed by `portal.ntangible.co`.
- **Confirmed routes:**
  - `https://ntangible.co/alliance`
  - `https://ntangible.co/fss`
  - `https://ntangible.co/cfs`
- **Underlying iframe targets found in code:**
  - `https://portal.ntangible.co/leaderboard/Alliance`
  - `https://portal.ntangible.co/leaderboard/FSS`
  - `https://portal.ntangible.co/leaderboard/2025-CFS`
- **Relevance to us:** These are public data surfaces outside the normal social channels and may be valuable for event-based content context.

### The team page exposes named leadership and a direct founder LinkedIn profile
- **Source:** team-page bundle | **Trust:** Tier 1
- **What was found:** The public team bundle contains structured profile data for company leadership and advisors.
- **Confirmed items:**
  - Founder/CEO: `Dan Connerty`
  - Founder LinkedIn: `https://www.linkedin.com/in/danconnerty/`
  - Additional named advisors surfaced publicly:
    - `Dr. Ed Levine`
    - `Dr. Jon Levine`
    - `Dr. Jacob Hyde`
    - `Howie Schwartz`
- **Relevance to us:** These public people entities can be modeled in the content brain as authors, spokespersons, and subject-matter references.

### The site embeds specific public YouTube videos that can be collected directly
- **Source:** testimonials, coaches, and recruiters bundles plus YouTube public oEmbed | **Trust:** Tier 1
- **What was found:** The site hardcodes public YouTube video IDs for testimonial and product content. These resolve publicly under the `@NTANGIBLE` channel.
- **Confirmed embedded videos:**
  - `xVD3_NtfdHQ` — `NTangible - Northwood University AD Testimonial`
  - `Zz7vxS_itmM` — `NTANGIBLE Testimonial - Frank Catalanotto`
  - `r7yuXV3P8QQ` — `NTangible - Hannah Wells Testimonial`
  - `hRSINmXP7nM` — `NTangible - Kai Minor Testimonial`
  - `4H0HWvv2De4` — `NTangible Testimonial - Carleton University Baseball`
  - `zE7BPW_hPKM` — `NTangible Testimonial - University of Waterloo Baseball`
  - `spKsM_5c0iM` — `NTangible NControl Product Demo`
  - `NMKUJfjI_HQ` — `NTangible Recruiting Dashboard Promo`
- **Relevance to us:** These are first-class public content assets and should be collected as individual content items, not just inferred from the YouTube channel.

### Public partner-owned pages and articles reference NTangible directly
- **Source:** partners-page bundle plus public partner-site HTML | **Trust:** Tier 1
- **What was found:** NTangible appears on multiple partner-owned public pages that are collectable without NTangible access.
- **Confirmed partner targets:**
  - Alliance partner page: `https://thealliancefastpitch.com/partners-ntangible/`
    - page title observed: `The Alliance Fastpitch - NTangible`
  - Alliance article: `https://thealliancefastpitch.com/blog/2025/04/16/mind-over-matter-how-big-time-athletes-build-unbreakable-mental-games/`
    - page title observed: `Mind Over Matter: How Big-Time Athletes Build Unbreakable Mental Games - The Alliance Fastpitch`
    - explicit byline text observed: `Written by NTangible, Alliance Fastpitch’s Official Mental Performance Partner.`
  - High Level Throwing page: `https://highlevelthrowing.com/pages/ntangible-assessment`
    - page title/OG title observed: `NTangible Assessment`
  - Future Stars Series article: `https://futurestarsseries.com/ntangible-adds-unique-clutch-performance-angle-to-player-evaluation-development-for-future-stars-series-events/`
    - page title observed: `NTANGIBLE adds unique 'clutch performance' angle to player evaluation, development for Future Stars Series events`
- **Important limit:** The RFK Racing partner URL currently hardcoded in the live NTangible partners page resolves to `Page Not Found` on RFK's site, so it should be treated as stale unless another live RFK NTangible page is found.
- **Relevance to us:** Partner-owned pages are useful content-brain sources because they preserve announcements, co-marketing copy, and NTangible-authored articles outside NTangible's own domain.

### An older NTangible-hosted announcement archive existed on the previous site
- **Source:** archived sitemap plus archived `hlt` article page | **Trust:** Tier 1
- **What was found:** The older Squarespace site had a dedicated `ntangibleannouncements` collection.
- **Historical routes exposed in the archived sitemap:**
  - `https://www.ntangible.co/ntangibleannouncements`
  - `https://www.ntangible.co/ntangibleannouncements/hlt`
  - `https://www.ntangible.co/ntangibleannouncements/probility`
  - `https://www.ntangible.co/ntangibleannouncements/Blog Post Title One-mrl7n`
- **Confirmed replayable article:**
  - `https://www.ntangible.co/ntangibleannouncements/hlt`
  - title observed: `NTangible Partners with High Level Throwing as Launch Partner for Breakthrough Softball Assessment and Data Integration`
  - author observed: `Dan Connerty`
  - published date observed: `September 12, 2024`
  - embedded media observed: Vimeo video `https://vimeo.com/956639755` titled `Austin Talking about High Level Throwing - Promo Video 2024`
- **Important limit:** In CDX checks, only the `hlt` announcement had a directly replayable archived page. The `probility` and `Blog Post Title One-mrl7n` routes are currently evidenced by the archived sitemap but did not produce matching replayable page captures in this investigation.
- **Relevance to us:** This is a strong historical source because it shows NTangible previously published its own announcement/blog content, and at least one full article body is recoverable.

### The archived sitemap reveals older public page taxonomy that no longer exists on the current React site
- **Source:** archived `sitemap.xml` from July 13, 2025 | **Trust:** Tier 1
- **What was found:** The old Squarespace site exposed a broader page inventory than the current app.
- **Historical routes found in the sitemap:**
  - `https://www.ntangible.co/our-validation`
  - `https://www.ntangible.co/home`
  - `https://www.ntangible.co/ncaabaseball`
  - `https://www.ntangible.co/teamfi`
  - `https://www.ntangible.co/ncaasoftball`
  - `https://www.ntangible.co/testimonials`
  - `https://www.ntangible.co/home-1`
- **Important limit:** Several of these routes are known from sitemap metadata only. During this pass, Wayback replay for `our-validation`, `ncaabaseball`, `teamfi`, and `ncaasoftball` returned Wayback index pages rather than preserved page bodies.
- **Relevance to us:** Even when the full page body is unavailable, the sitemap still preserves important historical taxonomy and topic coverage for the content brain.

### Website history is partially recoverable through the Wayback Machine
- **Source:** Internet Archive CDX API | **Trust:** Tier 1
- **What was found:** Public Wayback snapshots exist for the NTangible root domain.
- **Observed snapshot coverage:**
  - earliest root snapshots in returned sample: `2024-09-15`
  - additional captures in `2024-12`, `2025-07`, `2025-08`, and `2026-02` onward
- **Important limit:** In a quick CDX check, `ntangible.co/team-1` and `ntangible.co/research` did not return archived 200 snapshots directly, even though legacy/SPA route evidence exists elsewhere.
- **Relevance to us:** Wayback is useful for historical homepage snapshots and bundle discovery, but not every client-side route is guaranteed to have its own archived page.

### Historical social coverage changed over time
- **Source:** Wayback homepage snapshots from `2024-09-15` and `2025-07-13` | **Trust:** Tier 1
- **What was found:**
  - The September 15, 2024 archived homepage exposed Instagram only.
  - The July 13, 2025 archived homepage exposed Instagram, TikTok, LinkedIn, and YouTube.
- **Confirmed historical handle/link:**
  - TikTok: `http://tiktok.com/@ntangiblesports`
- **Inference:** NTangible expanded its public social footprint between late 2024 and mid-2025.
- **Relevance to us:** Historical discovery should include archived social links because not every handle remains linked from the current site.

### A likely predecessor brand exists: `Clutch Factor`
- **Source:** public F6S founder/company profiles and public YouTube metadata | **Trust:** Tier 2
- **What was found:** Public founder/startup profiles tie Dan Connerty to an earlier company/brand called `Clutch Factor`, which appears tightly related to NTangible's current pressure-performance positioning.
- **Confirmed public evidence:**
  - Dan Connerty F6S profile lists him as `CEO @Clutch Factor`
  - the same profile places him in `Toronto, Canada`
  - the profile shows an older email domain under `theclutchfactor.com`
  - a public Clutch Factor YouTube video resolves at `https://www.youtube.com/watch?v=tCm3B2rBWDI`
    - title: `Clutch Factor - Jayna Hefford - Will you be ready?`
    - author/channel: `Clutch Factor`
    - handle: `@clutchfactor5434`
    - description begins: `Clutch performance is generally thought of as a single moment in time...`
- **Important inference:** This strongly suggests that some older NTangible-relevant public content may live under `Clutch Factor` rather than `NTangible`.
- **Relevance to us:** Future public-only searches should include both `NTangible` and `Clutch Factor` terms when looking for older posts, videos, interviews, articles, or social surfaces.

### Public LinkedIn content exists outside the company-page URL
- **Source:** targeted public web search and indexed LinkedIn pages | **Trust:** Tier 2
- **What was found:** At least some NTangible-related LinkedIn content is publicly indexable even without LinkedIn admin access.
- **Confirmed examples:**
  - Dan Connerty article: `https://www.linkedin.com/pulse/ntangible-2025-mit-sloan-sports-analytics-conference-dan-connerty-uelwc`
    - title observed: `NTangible @ 2025 MIT Sloan Sports Analytics Conference`
    - published date observed in indexed page: `March 13, 2025`
  - William Carroll post: `https://www.linkedin.com/posts/injuryexpert_absolutely-huge-announcements-coming-after-activity-7275803510082883584-FBHZ`
    - lead text observed: `Absolutely huge announcements coming after the holidays for NTangible.`
    - published date observed in page JSON-LD: `December 20, 2024`
  - FoundersPress post: `https://www.linkedin.com/posts/founders-press_top-20-canadian-entrepreneurs-to-watch-in-activity-7417674235864571904-hEN3`
    - title observed: `Top 20 Canadian Entrepreneurs to Watch in 2026 - FoundersPress`
    - page body explicitly includes `Dan Connerty – Founder, NTangible`
- **Relevance to us:** LinkedIn company-page collection will remain incomplete without access, but public indexed posts/articles can still be added opportunistically to the content brain.

### Public press and awards coverage adds more NTangible article surfaces
- **Source:** targeted public web search and direct page fetches | **Trust:** Tier 2
- **What was found:** Multiple public press pages and award-related articles mention NTangible and Dan Connerty directly.
- **Confirmed examples:**
  - FoundersPress RFK article:
    - URL: `https://thefounderspress.com/ntangible-brings-mental-fitness-tech-to-rfk-elevate-pit-crew-performance/`
    - title observed: `NTangible Brings Mental Fitness Tech to RFK Racing in Push to Elevate Pit Crew Performance`
    - author observed: `Eric Rafat`
    - published date observed: `July 9, 2025`
  - Youth Sports Business Report awards article:
    - URL: `https://youthsportsbusinessreport.com/youth-sports-business-report-and-gofundme-announce-nominees-for-the-inaugural-youth-sports-awards-across-10-categories/`
    - title observed: `Youth Sports Business Report and GoFundMe Announce Nominees for the Inaugural Youth Sports Awards Across 10 Categories`
    - published date observed: `March 9, 2026`
  - Le Metropolitain Entrepreneur Challenge article:
    - URL: `https://lemetropolitain.com/lintelligence-artificielle-sinvite-a-lentrepreneur-challenge/`
    - title observed: `L’intelligence artificielle s’invite à l’Entrepreneur Challenge`
    - article body mentions Dan Connerty and NTangible directly
  - L'Express Entrepreneur Challenge article:
    - URL: `https://l-express.ca/entrepreneur-challenge-2025-lia-gagne-contre-lia/`
    - title observed: `Entrepreneur Challenge 2025 : l’IA gagne contre l’IA`
    - article body mentions Dan Connerty and shows him presenting the company
  - MotorsportsNews RFK article:
    - URL: `https://www.motorsportsnews.net/2025/07/08/rfk-racing-joins-forces-with-ntangible-as-official-mental-fitness-partner-enhancing-pit-crew-performance-through-groundbreaking-assessment/`
    - title observed: `RFK Racing Joins Forces with NTangible as Official Mental Fitness Partner, Enhancing Pit Crew Performance Through Groundbreaking Assessment`
    - author observed: `Mike`
    - published date observed: `July 8, 2025`
- **Relevance to us:** These are public, article-style content sources outside NTangible's own domain and add coverage of partnerships, recognition, and founder activity that would otherwise be missing from a public-only backfill.

### Public leadership/advisory pages add useful company-context bios
- **Source:** targeted public web search and direct page fetches | **Trust:** Tier 2
- **What was found:** At least one public advisory-board page outside NTangible's own site contains explicit NTangible mentions in leadership bios.
- **Confirmed example:**
  - The Captains Agency advisory board:
    - URL: `https://thecaptainsagency.com/advisory-board`
    - title observed: `Advisory Board`
    - body text includes Will Carroll's bio with `now NTangible`
    - body text includes a separate Dan Connerty advisory-board entry labeled `Ntangible`
- **Relevance to us:** This is useful enrichment for the content brain because it adds externally published leadership context without depending on private bios or internal documents.

### No confirmed public X account or public newsletter archive was found
- **Source:** live site bundle, archived site snapshots, and targeted public web search | **Trust:** Tier 2
- **What was found:**
  - No X/Twitter profile URL is hardcoded in the live site bundle.
  - No X/Twitter profile URL was surfaced from the archived 2024 or 2025 homepage snapshots either.
  - Targeted public web searches did not surface a confidently confirmed NTangible X profile.
  - No Mailchimp archive, Kit archive, Substack, Beehiiv, or public browser-view newsletter archive was surfaced from the website or targeted searches.
- **Relevance to us:** We should proceed assuming:
  - X is **unconfirmed**
  - public newsletter archive is **unconfirmed**
  - LinkedIn newsletter is **unconfirmed**

## Synthesis
The file and public web evidence were enough to identify most of the starting inventory needed for a public-only collection run.

Since the first pass, the strongest additions were public LinkedIn article/post URLs and several external press pages about NTangible. Those sources move the corpus closer to a broad public history of the brand even without account access. The biggest remaining public-only blind spots are still the same: deeper historical Instagram extraction, any unconfirmed X presence, any public newsletter archive, and private analytics that are impossible to recover without NTangible cooperation.

### Hard-confirmed starting points
- Website: `https://ntangible.co/`
- Instagram: `https://www.instagram.com/ntangiblesports`
- LinkedIn company page: `https://www.linkedin.com/company/ntangible/`
- YouTube: `https://www.youtube.com/channel/UC6k2GMbwnIGyEOzXKPZZpWQ`
- YouTube handle: `https://www.youtube.com/@NTANGIBLE`
- Calendly: `https://calendly.com/ntangible/30min`
- Support email: `support@ntangible.co`
- Portal login: `https://portal.ntangible.co/login/`
- Public leaderboards:
  - `https://ntangible.co/alliance`
  - `https://ntangible.co/fss`
  - `https://ntangible.co/cfs`
- Public research docs:
  - four dated Google Drive paper URLs listed above

### Strong website-content collection targets
- SPA bundle route extraction from `index-*.js`
- research-page bundle extraction from `Research-*.js`
- Wayback snapshots of the root site
- archived sitemap extraction from the old Squarespace site
- public Instagram profile/posts
- public YouTube channel/videos
- YouTube RSS feed metadata
- partner-owned public pages/articles
- public LinkedIn articles/posts surfaced in search indexes
- public testimonial and product-tour videos hardcoded in site bundles
- archived `ntangibleannouncements/hlt` article content
- historical `Clutch Factor` public surfaces

### Still unconfirmed
- Public X handle/profile
- Public newsletter archive
- Public LinkedIn newsletter page
- Any public X-era archive that predates the current site

### Practical conclusion
You asked whether I could find "all of this information" from the file. The answer is:
- **yes** for the core public inventory needed to begin a no-access collection run
- **no** for X/newsletter completeness, because those public surfaces were not confirmed from the available evidence

This means the next implementation can start immediately with:
- website + SPA route harvesting
- Instagram
- LinkedIn company URL as a known target
- YouTube
- YouTube RSS feed
- embedded testimonial/product videos
- partner-owned articles/pages
- archived historical sitemap routes
- archived `ntangibleannouncements/hlt` article content
- predecessor-brand lookups under `Clutch Factor`
- research papers
- Wayback

And it should treat:
- X
- newsletters
- LinkedIn newsletter

as optional later additions if further evidence appears.

## Relevance
HIGH

## METHODOLOGY.md Update
No `METHODOLOGY.md` exists in this repo. If one is added later, include: "Derive public collection targets from the live site bundle first, then verify handles/archives from public metadata and Wayback before building collectors."
