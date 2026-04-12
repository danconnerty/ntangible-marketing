# X (Twitter) API Pricing — April 2026

## Tier Summary

| Tier | Cost | Post Limit | Read Limit | Notes |
|------|------|-----------|------------|-------|
| **Free** | $0 | 1,500/month (~50/day) | None (write-only) | Can post tweets, upload media. Cannot read timelines, like, retweet, or pull analytics. |
| **Basic** | $200/mo | 3,000/month | 50K tweets/month | Adds read access. Minimum for pulling engagement metrics. |
| **Pro** | $5,000/mo | 300,000/month | 1M tweets/month | Full access. Overkill for Phase 1. |
| **Enterprise** | $42,000+/mo | Custom | Firehose | Not relevant. |

## Key Constraints

- **Free tier** technically supports posting via `POST /2/tweets` (OAuth 2.0 PKCE or OAuth 1.0a). Sufficient for Phase 1 content volume.
- **Programmatic replies** (Feb 2026 change): On all self-serve tiers, replying via API now requires the original author to @mention you or quote your post. Enterprise exempt.
- **Media upload** still uses OAuth 1.0a while tweet creation uses OAuth 2.0 — apps need dual auth.
- **Analytics/engagement data** requires at minimum Basic ($200/mo). Free tier cannot read tweet metrics.
- **Like endpoint** removed from Free tier as of Aug 2025.
- X has changed pricing/policies multiple times since 2023 — always verify at developer.x.com.

## Recommendation for Phase 1

Start with **Free tier** for posting ($0). The ~50 tweets/day limit covers the blueprint's cadence (1-2 hot takes + 3-4 data drops + 1-2 threads/week ≈ 10-15 tweets/day). Upgrade to **Basic ($200/mo)** when you need analytics/engagement tracking (Phase 6).

## Relevance
HIGH
