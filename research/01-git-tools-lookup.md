# Git Tools for NTangible Marketing Engine Blueprint

## Research Question
Identify existing open-source GitHub tools that can accelerate the blueprint implementation for multi-agent social publishing, content scheduling, approval workflows, analytics, compliance, and newsletter operations.

## Key Findings

### [postiz-app](https://github.com/gitroomhq/postiz-app)
- **Source:** GitHub repository
- **What they did:** Self-hosted, multi-platform social scheduling system with OAuth-based platform posting and AI assistance.
- **Relevance:** Strong baseline for the core scheduler/dashboard slice (Phase 1-3). Includes official platform integrations and approval/privacy posture.
- **Fit notes:** Good candidate for adapting into your orchestrator as the content publishing and queueing core.

### [mixpost](https://github.com/inovector/mixpost)
- **Source:** GitHub repository (3.1k stars)
- **What they did:** Buffer-like self-hosted scheduling/publishing and content/calendar workflows.
- **Relevance:** Useful for Phase 2 scheduler/calendar baseline; includes cross-platform posting and content management flows.
- **Fit notes:** Less AI-native than your blueprint, so it can be wrapped with your content pipeline rather than used as-is for generation.

### [social-media-agent](https://github.com/langchain-ai/social-media-agent)
- **Source:** GitHub repository
- **What they did:** Social posting agent with prompt + scheduling behavior and human-in-the-loop controls.
- **Relevance:** Useful reference for Agent-centric prompt structuring and structured platform-specific rules.
- **Fit notes:** Useful for Content Writer + agent-level style logic patterns.

### [social-media-agents](https://github.com/Klaudiusz321/social-media-agents)
- **Source:** GitHub repository
- **What they did:** Multi-agent social system with brand guideline schema, LinkedIn/X/IG support, scheduling, and compliance requirements in config files.
- **Relevance:** Good proof-of-concept for your agent hierarchy, including brand-guideline JSON and platform-specific content rules.
- **Fit notes:** Validate before production use; appears more academic/project-style than enterprise production.

### [agent-social-marketing](https://github.com/agentuity/agent-social-marketing)
- **Source:** GitHub repository
- **What they did:** Multi-agent social content workflow (manager + copywriter + scheduler) from idea to scheduling.
- **Relevance:** Closest conceptual match for your 8-agent blueprint shape (though unstable by repo message).
- **Fit notes:** Use as architecture reference only unless you are okay with a rapidly changing dependency stack.

### [n8n](https://github.com/n8n-io/n8n)
- **Source:** GitHub repository
- **What they did:** Self-hostable workflow automation platform with 400+ integrations and AI nodes.
- **Relevance:** Good for event-driven orchestration glue in Phases 2, 5, 6, 7, and webhook integrations.
- **Fit notes:** Very useful for rapid workflow composition; still requires strict hardening around secrets and trigger flow controls.

### [crewAI](https://github.com/crewAIInc/crewAI)
- **Source:** GitHub repository
- **What they did:** General-purpose multi-agent orchestration framework.
- **Relevance:** Useful for orchestrator internals and role-based agent decomposition.
- **Fit notes:** Does not provide social connectors; pair with Postiz/Mixpost/n8n/API layer.

### [promptfoo](https://github.com/promptfoo/promptfoo)
- **Source:** GitHub repository
- **What they did:** LLM prompt testing, red teaming, and CI-driven evaluation.
- **Relevance:** Critical for enforcing voice/compliance reliability of generated posts before publish.
- **Fit notes:** Integrate in CI and a pre-publish validation pipeline.

### [langfuse](https://github.com/langfuse/langfuse)
- **Source:** GitHub repository
- **What they did:** LLM observability, tracing, prompt/version management, and eval workflows.
- **Relevance:** Important for Analytics Agent + loop improvements and troubleshooting generation quality.
- **Fit notes:** Helps close the loop for “what works by platform, segment, post type.”

### [listmonk](https://github.com/knadh/listmonk)
- **Source:** GitHub repository (19.4k stars)
- **What they did:** Self-hosted newsletter and list manager.
- **Relevance:** Strong fit for Phase 10 monthly newsletter and audience segmentation.

### [keila](https://github.com/pentacent/keila)
- **Source:** GitHub repository (2.1k stars)
- **What they did:** Open-source newsletter tool with campaign/editor and provider support (SES/Sendgrid/etc).
- **Relevance:** Alternative to Mailchimp/hosted ESP for newsletter generation and sending.

### [mailtrain](https://github.com/Mailtrain-org/mailtrain)
- **Source:** GitHub repository
- **What they did:** Self-hosted newsletter app with segmenting, templates, automation workflows, and multi-endpoint sending.
- **Relevance:** Enterprise-style option for newsletter infra if listmonk/Keila isn’t a fit.

### [Mautic](https://github.com/mautic)
- **Source:** GitHub repository
- **What they did:** Full marketing automation platform with campaigns, leads, and segmentation.
- **Relevance:** Useful reference for lead nurture + partner/customer workflow and consent/segment handling.
- **Fit notes:** Heavy to operate; best if you need broader marketing automation beyond social.

## Synthesis
No single GitHub project fully matches your full blueprint (AI generation + partner-data event triggers + strict brand guardrails + cross-platform routing + partner delivery + blog repurposing + analytics feedback + newsletter). Best approach is composable:
- Use **Postiz or Mixpost** as the publishing backbone,
- Use **n8n/crewAI or similar agent framework** as orchestrator glue,
- Use **social-media-* repos** as content/agent design examples,
- Add **Promptfoo + Langfuse** for quality/guardrails and feedback loop.

The result is a hybrid stack where existing OSS handles durable parts (scheduling, workflow, observability, newsletters) and your team owns blueprint-specific logic (partner triggers, score thresholds, brand controls, repurposing policy).

## Additional Git Scans (April 2026)

Useful follow-up picks (especially if you want alternatives or older archives):

- [`TechSquidTV/Shoutify`](https://github.com/TechSquidTV/Shoutify)
  - Open-source, self-hosted social media management concept, but currently archived/read-only and explicitly not production-ready.
- [`AwesomeSelfhosted/SociaBoard`](https://github.com/AwesomeSelfhosted/SociaBoard)
  - Social management platform with reporting/analytics intent, but has very low activity and is now mainly a niche legacy repo.
- [`huginn/huginn`](https://github.com/huginn/huginn)
  - Event-driven automation engine (“hackable IFTTT/Zapier on self-host”). Strong for triggers and webhooks, weak for native social posting quality/approval workflows.
- [`LangGraph/LangGraph` + hosted social examples](https://github.com/langchain-ai/langgraph)
  - Not in the shortlist above, but relevant for orchestration/stateful agent workflows if you want to own everything in LangChain stack; combine with scheduler connectors for posting.
- [`mailtrain-org/mailtrain`](https://github.com/Mailtrain-org/mailtrain)
  - Newsletter automation with segmentation/campaigns and stronger enterprise deployment footprint than lightweight tools.

Observed pattern from April 2026: no mature all-in-one OSS stack fully covers the blueprint with native X/LinkedIn/Instagram publishing, approval + compliance + analytics + repurposing. The best practical path remains modular, with a social scheduler as core and a separate orchestrator/agent layer.

## Relevance
HIGH

## METHODOLOGY.md Update
Recommend adding a “Tooling strategy” note: *Start with a composable stack using Postiz + n8n + prompt validation tooling, and avoid monolithic all-in-one replacements.*
