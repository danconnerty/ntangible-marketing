# Existing Open-Source Projects Closest to the NTangible Marketing Engine

## Research Question
Which current open-source projects already implement meaningful parts of the NTangible marketing-engine blueprint: multi-platform social publishing, AI-assisted content generation, workflow orchestration, analytics/feedback, partner-trigger style automation, and newsletter operations?

## Key Findings

### [gitroomhq/postiz-app](https://github.com/gitroomhq/postiz-app)
- **Source:** GitHub repository
- **What it does:** Self-hosted social media scheduling platform with AI features, analytics, collaboration, API access, and automation-friendly integrations.
- **Why it matters:** Closest production-grade match for the social publishing/dashboard part of the blueprint.
- **Best fit:** Publishing core, content calendar, team workflows, analytics baseline.
- **Missing pieces:** Partner-event ingestion, domain-specific agent logic, revenue-content strategy, newsletter segmentation.

### [inovector/mixpost](https://github.com/inovector/mixpost)
- **Source:** GitHub repository
- **What it does:** Self-hosted Buffer-style social media management with queue/calendar workflows, platform variants, analytics, templates, and team collaboration.
- **Why it matters:** Strong alternative publishing backbone if you want a simpler social scheduler than building one from scratch.
- **Best fit:** Scheduler, calendar, post variants, platform-specific content ops.
- **Missing pieces:** Agentic orchestration, partner-trigger pipelines, deeper AI workflow logic.

### [langchain-ai/social-media-agent](https://github.com/langchain-ai/social-media-agent)
- **Source:** GitHub repository
- **What it does:** Agent that sources content from URLs, generates LinkedIn/X posts, supports scheduling, and uses human-in-the-loop review.
- **Why it matters:** Closest match for the AI-agent part of the blueprint, especially post generation plus review.
- **Best fit:** Content-writer agent, workflow graph patterns, prompt structure, scheduling integration.
- **Missing pieces:** Full marketing operating system, broad dashboarding, partner data ingestion, autonomous multi-channel orchestration at business scale.

### [agentuity/agent-social-marketing](https://github.com/agentuity/agent-social-marketing)
- **Source:** GitHub repository
- **What it does:** Multi-agent content marketing system with manager, copywriter, and scheduler agents, scheduling through Typefully.
- **Why it matters:** Very close to the blueprint’s manager/content-writer/scheduler decomposition.
- **Best fit:** Multi-agent architecture reference for orchestrator, campaign state, and handoffs.
- **Missing pieces:** Full production publishing stack, partner workflows, analytics loop, compliance rules, Instagram/LinkedIn breadth.

### [Klaudiusz321/social-media-agents](https://github.com/Klaudiusz321/social-media-agents)
- **Source:** GitHub repository
- **What it does:** Modular multi-agent social media system with trend scanning, content creation, brand-guideline management, schedulers, and platform posters.
- **Why it matters:** Best conceptual mirror of the blueprint’s specialized agents.
- **Best fit:** Agent boundaries, brand-guideline schema, dry-run support, scheduler logic.
- **Missing pieces:** Mature product surface, durable infra, partner-delivery system, enterprise-grade workflows.

### [n8n-io/n8n](https://github.com/n8n-io/n8n)
- **Source:** GitHub repository
- **What it does:** Workflow automation platform with 400+ integrations and native AI capabilities.
- **Why it matters:** Best glue layer for event-triggered workflows, partner webhooks, CRM actions, Slack delivery, and campaign automation.
- **Best fit:** Orchestration glue, trigger routing, webhook processing, non-code operations.
- **Missing pieces:** Social product UX, marketing-specific agent roles, opinionated content system.

### [knadh/listmonk](https://github.com/knadh/listmonk)
- **Source:** GitHub repository
- **What it does:** Self-hosted newsletter and mailing-list manager.
- **Why it matters:** Strong fit for the newsletter segment of the blueprint without building email infrastructure yourself.
- **Best fit:** Monthly newsletter delivery, list management, segmentation baseline.
- **Missing pieces:** Social publishing, AI generation, campaign orchestration.

### [mautic/mautic](https://github.com/mautic/mautic)
- **Source:** GitHub repository
- **What it does:** Open-source marketing automation platform for campaigns, journeys, and email marketing.
- **Why it matters:** Strongest existing OSS option for broader marketing automation and nurture flows.
- **Best fit:** Lead nurture, campaign automation, audience segmentation.
- **Missing pieces:** AI-first agent architecture, modern social publishing ergonomics.

### [langfuse/langfuse](https://github.com/langfuse/langfuse)
- **Source:** GitHub repository
- **What it does:** Observability, evals, prompt management, datasets, and experimentation for LLM applications.
- **Why it matters:** Best fit for the analytics/evaluation loop behind agent quality and prompt improvement.
- **Best fit:** Tracing, prompt versioning, evaluation, operational visibility for AI agents.
- **Missing pieces:** Actual social publishing and marketing workflows.

## Synthesis
No single open-source project currently covers the full NTangible blueprint end-to-end.

The closest practical stack is composable:
- **Postiz** or **Mixpost** for social publishing and calendar operations
- **LangChain Social Media Agent**, **agent-social-marketing**, or **social-media-agents** for the content-agent layer
- **n8n** for partner/event-driven orchestration and delivery workflows
- **Langfuse** for agent tracing/evals
- **listmonk** or **Mautic** for newsletter and nurture systems

If the goal is to build quickly, the best path is usually:
1. adopt **Postiz** or **Mixpost** as the social backbone,
2. add a thin custom orchestrator for NTangible-specific rules and partner triggers,
3. use **n8n** for integration plumbing,
4. layer in **Langfuse** for observability,
5. connect **listmonk** or **Mautic** later for email.

## Relevance
HIGH
