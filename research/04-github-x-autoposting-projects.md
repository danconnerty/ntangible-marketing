# GitHub Projects: AI-Powered X Auto-Posting — April 2026

## Best References for Phase 1

### Architecture References

| Project | Stars | Stack | Best For | Status |
|---------|-------|-------|----------|--------|
| [langchain-ai/social-media-agent](https://github.com/langchain-ai/social-media-agent) | ~2,459 | TypeScript, LangGraph | Agent architecture + approval workflows | Very active (Apr 2026) |
| [garyb9/twitter-llm-bot](https://github.com/garyb9/twitter-llm-bot) | ~51 | Python, FastAPI, Tweepy, APScheduler, LangChain | Closest clean Python reference for Phase 1 | Nov 2024 |
| [Klaudiusz321/social-media-agents](https://github.com/Klaudiusz321/social-media-agents) | ~18 | Python | Multi-agent with brand guidelines schema | Active (Apr 2026) |

### X API Integration References

| Project | Stars | Best For | Notes |
|---------|-------|----------|-------|
| [Infatoshi/x-cli](https://github.com/Infatoshi/x-cli) | ~341 | Cleanest OAuth2 PKCE flow for X API v2 in Python | Active (Mar 2026) |
| [tweepy/tweepy](https://github.com/tweepy/tweepy) | ~11,152 | Industry-standard Python X API client (v2 + v1.1) | Active |
| [lewispour/Twitter-auto-Post-Bot](https://github.com/lewispour/Twitter-auto-Post-Bot---X.com---Tweepy-python-bot) | ~65 | Simple Tweepy + OpenAI posting with web UI | Active (Mar 2026) |

### Brand Voice / Compliance References

| Project | Stars | Best For | Notes |
|---------|-------|----------|-------|
| [ericosiu/ai-marketing-skills](https://github.com/ericosiu/ai-marketing-skills) | - | Voice markers, banned words, scoring patterns | Extractable compliance patterns |
| [blacktwist/social-media-skills](https://github.com/blacktwist/social-media-skills) | ~59 | Content strategy prompts, brand voice analysis | Active (Apr 2026), shell-based |

### Publishing Backbone

| Project | Stars | Best For | Notes |
|---------|-------|----------|-------|
| [gitroomhq/postiz-app](https://github.com/gitroomhq/postiz-app) | ~27,903 | Full scheduling UI + multi-platform publishing | TypeScript, very active |

### Scraping-Based (ToS Risk — Dev/Test Only)

| Project | Stars | Best For | Notes |
|---------|-------|----------|-------|
| [d60/twikit](https://github.com/d60/twikit) | ~4,253 | Bypass API limits, no API key needed | Violates X ToS, account ban risk |
| [ihuzaifashoukat/twitter-automation-ai](https://github.com/ihuzaifashoukat/twitter-automation-ai) | ~118 | Multi-account Selenium automation with LLM | Fragile, ToS risk |
| [nirholas/XActions](https://github.com/nirholas/XActions) | ~185 | MCP server for AI agents to interact with X | Interesting MCP pattern, scraping-based |

### Previously Identified — Status Updates

- **agentuity/agent-social-marketing** — Stale (last pushed Jun 2025). Not recommended.
- **postiz-app** — Grown to 28K stars. Dominant OSS social scheduling platform.
- **langchain-ai/social-media-agent** — Now the most mature agent-based social posting system. TypeScript/LangGraph.

## What No Project Does Well (Must Build)

1. **Claude-specific content generation pipeline** — Most use OpenAI. Needs prompt engineering for Anthropic SDK.
2. **Brand voice compliance gate** — No project enforces banned phrases, trademark rules, tone scoring end-to-end.
3. **Content intent tagging** — No project tags posts as Brand/Partner/Revenue for separate tracking.
4. **Analytics feedback loop** — No project closes the loop from engagement metrics back to content generation parameters.

## X API Client Library Recommendation

Use **Tweepy** (11K stars, industry standard) for official X API v2 posting. Reference **x-cli** for OAuth2 PKCE flow implementation.

## Relevance
HIGH
