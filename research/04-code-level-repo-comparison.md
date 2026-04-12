# Code-Level Comparison of Existing GitHub Projects

## Research Question
Which of the shortlisted GitHub projects are closest to the NTangible marketing-engine blueprint when you inspect their actual code structure, not just their README claims?

## Repos Inspected
- `gitroomhq/postiz-app`
- `inovector/mixpost`
- `langchain-ai/social-media-agent`
- `agentuity/agent-social-marketing`

## Findings

### 1. Postiz is the strongest production publishing backbone

Why:
- It is a real monorepo with separate backend, frontend, SDK, and orchestrator apps.
- The orchestrator uses Temporal workflows for recurring automation and retries.
- It already has broad social provider support in a reusable integration layer.
- It has real API routes for autoposting, analytics, integrations, media, notifications, and an AI/copilot surface.

Code evidence:
- `apps/orchestrator/src/workflows/autopost.workflow.ts` runs an hourly infinite autopost loop with Temporal retries.
- `apps/orchestrator/src/activities/post.activity.ts` handles provider selection, media transformation, posting, comments, and streak workflows.
- `apps/backend/src/api/routes/autopost.controller.ts` exposes CRUD endpoints for autopost configs.
- `apps/backend/src/api/routes/copilot.controller.ts` exposes a chat/agent endpoint and thread memory retrieval.
- `libraries/nestjs-libraries/src/integrations/social/*` contains a large provider matrix.

Assessment:
- Best choice if you want a **real product base** for scheduling/publishing.
- Weakest part relative to NTangible: the domain-specific “marketing brain” is still generic.

### 2. Social Media Agent is the strongest agent architecture reference

Why:
- It is a real LangGraph system, not a toy script.
- It has distinct graphs for curation, report generation, post generation, thread generation, repurposing, verification, and upload.
- It supports human-in-the-loop review, scheduling, image generation/validation, and multi-source ingestion.

Code evidence:
- `src/agents/supervisor/supervisor-graph.ts` fans out curated content into parallel report-generation runs, then groups and turns them into posts.
- `src/agents/generate-post/generate-post-graph.ts` defines the end-to-end graph: auth, verify links, generate report, generate post, condense, image selection, HITL, rewrite, schedule.
- `src/agents/upload-post/index.ts` contains actual Twitter and LinkedIn publishing logic plus Slack failure reporting.
- `src/agents/repurposer/index.ts` shows a dedicated repurposing graph.

Assessment:
- Best choice if you want a **real agent workflow reference** for orchestrator/content-writer logic.
- Weakest part relative to NTangible: it is not a full social SaaS platform and does not include partner data operations or a business dashboard.

### 3. Agent Social Marketing is the cleanest minimal multi-agent template

Why:
- It has the exact high-level shape you described: manager -> copywriter -> scheduler.
- The code is small and easy to understand.
- It uses a campaign object and hands off between agents explicitly.

Code evidence:
- `src/agents/manager/index.ts` normalizes input, extracts structure with an LLM, checks for duplicate campaigns, and hands off to the copywriter.
- `src/agents/copywriter/index.ts` generates LinkedIn posts and Twitter threads, stores them, then hands off to the scheduler.
- `src/agents/scheduler/index.ts` schedules output through Typefully.
- `src/types/index.ts` defines a compact campaign/content/scheduling data model.

Assessment:
- Best choice if you want a **small starting skeleton** to fork and extend quickly.
- Weakest part relative to NTangible: too thin for production. It lacks robust provider integrations, analytics, guardrails, partner workflows, and richer campaign ops.

### 4. Mixpost is a mature scheduler, not an agent system

Why:
- It has robust scheduling and provider abstractions, but almost no agentic behavior.
- The architecture is Laravel-style app logic around accounts, posts, provider managers, and queue jobs.

Code evidence:
- `src/Commands/RunScheduledPosts.php` scans pending scheduled posts and dispatches publishing.
- `src/Jobs/AccountPublishPostJob.php` enforces queue + rate-limit behavior per account.
- `src/Actions/AccountPublishPost.php` parses versioned content and sends it through the selected provider.
- `src/SocialProviders/Twitter/Concerns/ManagesResources.php` contains concrete platform posting and media-upload logic.

Assessment:
- Best choice if you only need a **scheduler/publisher base**.
- Weakest part relative to NTangible: almost none of the blueprint’s agentic strategy layer is present.

## Overall Ranking

### Closest to the blueprint as a whole
1. `postiz-app`
2. `social-media-agent`
3. `agent-social-marketing`
4. `mixpost`

### Best by category
- **Production social publishing backbone:** `postiz-app`
- **Agent orchestration reference:** `social-media-agent`
- **Smallest forkable multi-agent starter:** `agent-social-marketing`
- **Traditional scheduler/publisher:** `mixpost`

## Recommended Build Strategy

If the goal is to build the NTangible engine fast without rebuilding the world:

1. Use **Postiz** as the publishing/calendar/integrations base.
2. Borrow workflow ideas from **Social Media Agent** for curation, verification, repurposing, and HITL checkpoints.
3. Borrow the simple role split from **Agent Social Marketing** for the first custom NTangible agent layer.
4. Do not start from **Mixpost** unless you explicitly want a Laravel scheduler product and are willing to build the agent layer yourself.

## Bottom Line

If you want the fastest path to something real:
- **Fork Postiz** if you want a product.
- **Borrow Social Media Agent patterns** if you want the brains.
- **Borrow Agent Social Marketing structure** if you want the cleanest small agent skeleton.

The closest practical stack is still:
- `Postiz + custom NTangible orchestrator + optional LangGraph-style agent flows`

## Relevance
HIGH
