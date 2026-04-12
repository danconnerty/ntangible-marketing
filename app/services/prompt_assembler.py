import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.trigger import TriggerEvent
from app.models.workflow import Workflow, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.memory_retrieval import MemoryRetrievalService

logger = logging.getLogger(__name__)


class PromptAssembler:
    def __init__(self, db: Session):
        self.db = db

    def assemble(
        self,
        workflow: Workflow,
        version: WorkflowVersion,
        trigger: TriggerEvent,
    ) -> dict[str, Any]:
        """Build a generation-ready payload from workflow config, trigger context, and memory."""
        config = WorkflowVersionConfig(**version.config)
        routing = config.routing

        content_type = routing.target_content_type or workflow.content_type
        pillar = routing.target_pillar or "blind_spot"
        intent = routing.target_intent or "brand"
        raw_context = trigger.source_payload.get("request") or self._flatten_payload(trigger.source_payload)
        campaign_context = self._extract_campaign_context(
            trigger.source_payload,
            include_campaign_context=config.retrieval.include_campaign_context,
            configured_fields=config.retrieval.campaign_context_fields,
        )
        revenue_context = self._extract_revenue_context(
            trigger.source_payload,
            include_revenue_context=config.retrieval.include_revenue_context,
            configured_fields=config.retrieval.revenue_context_fields,
        )
        partner_context = self._extract_partner_context(trigger.source_payload)
        market_signal_context = self._extract_market_signal_context(
            trigger.source_payload,
            include_market_signals=config.retrieval.include_market_signals,
        )
        lead_context = self._extract_lead_context(trigger.source_payload)
        blog_context = self._extract_blog_context(trigger.source_payload)
        retrieval_query = " ".join(
            part
            for part in [
                raw_context,
                self._campaign_context_text(campaign_context) if campaign_context else "",
                self._revenue_context_text(revenue_context) if revenue_context else "",
                self._partner_context_text(partner_context) if partner_context else "",
                self._market_signal_context_text(market_signal_context) if market_signal_context else "",
                self._lead_context_text(lead_context) if lead_context else "",
                self._blog_context_text(blog_context) if blog_context else "",
            ]
            if part
        ) or workflow.name

        memory = MemoryRetrievalService(self.db)
        memory.sync_control_room_memory(limit=max(config.retrieval.max_examples * 20, 100))
        retrieval = memory.build_generation_context(
            query=retrieval_query,
            platform=workflow.platform,
            workflow_slug=workflow.slug,
            approved_limit=config.retrieval.max_examples,
            rejected_limit=min(2, config.retrieval.max_examples),
        )
        approved_text = self._examples_block("Approved examples", retrieval["approved_examples"])
        rejected_text = self._examples_block("Avoid repeating these rejected patterns", retrieval["rejected_examples"])
        facts_text = self._facts_block(retrieval.get("brain_facts", []))
        system = "\n\n".join(
            part
            for part in [
                f"Workflow: {workflow.name} ({workflow.platform.value})",
                f"Content type: {content_type}",
                f"Pillar: {pillar}",
                f"Intent: {intent}",
                f"Tone notes: {config.prompt.tone_notes}" if config.prompt.tone_notes else "",
                f"Prompt additions: {config.prompt.system_prompt_additions}" if config.prompt.system_prompt_additions else "",
                f"CTA preferences: {', '.join(config.cta.cta_preferences)}" if config.cta.cta_preferences else "",
                f"CTA rules: {config.cta.cta_rules}" if config.cta.cta_rules else "",
                self._campaign_context_text(campaign_context) if campaign_context else "",
                self._revenue_context_text(revenue_context) if revenue_context else "",
                self._partner_context_text(partner_context) if partner_context else "",
                self._market_signal_context_text(market_signal_context) if market_signal_context else "",
                self._lead_context_text(lead_context) if lead_context else "",
                self._blog_context_text(blog_context) if blog_context else "",
                facts_text,
            ]
            if part
        )
        if config.prompt.system_prompt_additions:
            system += f"\n\nADDITIONAL INSTRUCTIONS:\n{config.prompt.system_prompt_additions}"

        user = "\n\n".join(
            part
            for part in [
                f"Trigger context:\n{raw_context}" if raw_context else "",
                f"Campaign context:\n{self._campaign_context_text(campaign_context)}" if campaign_context else "",
                f"Revenue context:\n{self._revenue_context_text(revenue_context)}" if revenue_context else "",
                f"Partner context:\n{self._partner_context_text(partner_context)}" if partner_context else "",
                f"Market signal:\n{self._market_signal_context_text(market_signal_context)}" if market_signal_context else "",
                f"Lead context:\n{self._lead_context_text(lead_context)}" if lead_context else "",
                f"Blog context:\n{self._blog_context_text(blog_context)}" if blog_context else "",
                approved_text,
                rejected_text,
            ]
            if part
        )
        if config.assets.asset_instructions:
            user += f"\n\nASSET INSTRUCTIONS:\n{config.assets.asset_instructions}"
        if config.formatting.max_chars is not None:
            user += f"\n\nMAX CHARS: {config.formatting.max_chars}"
        if config.formatting.max_hashtags is not None:
            user += f"\nMAX HASHTAGS: {config.formatting.max_hashtags}"

        return {
            "system": system,
            "user": user,
            "context": user,
            "content_type": content_type,
            "pillar": pillar,
            "intent": intent,
            "platform": workflow.platform.value,
            "claims": [],
            "dynamic_value_groups": trigger.source_payload.get("dynamic_value_groups"),
            "partner_name": trigger.source_payload.get("partner_name"),
            "canva_template_id": trigger.source_payload.get("canva_template_id"),
            "publish_mode": trigger.source_payload.get("publish_mode"),
            "campaign": campaign_context,
            "campaign_context": campaign_context,
            "revenue_context": revenue_context,
            "partner_context": partner_context,
            "market_signal_context": market_signal_context,
            "lead_context": lead_context,
            "blog_context": blog_context,
            "retrieved_examples": retrieval,
            "retrieved_memory_ids": retrieval["memory_ids"],
            "workflow_version_config": config.model_dump(),
        }

    def _flatten_payload(self, payload: dict[str, Any]) -> str:
        values: list[str] = []
        for value in payload.values():
            if isinstance(value, dict):
                values.append(self._flatten_payload(value))
            elif isinstance(value, list):
                values.extend(str(item) for item in value)
            elif value is not None:
                values.append(str(value))
        return " ".join(values)

    def _examples_block(self, label: str, items: list[dict[str, Any]]) -> str:
        if not items:
            return ""
        lines = [label + ":"]
        for item in items:
            lines.append(f"- {item.get('title') or 'Example'}: {item.get('content', '')[:220]}")
        return "\n".join(lines)

    def _facts_block(self, facts: list[dict[str, Any]]) -> str:
        if not facts:
            return ""
        lines = ["Company context (factual grounding — use as background, not as content to imitate):"]
        for fact in facts:
            lines.append(f"- {fact['title']}: {fact['content'][:300]}")
        return "\n".join(lines)

    def _extract_campaign_context(
        self,
        payload: dict[str, Any],
        include_campaign_context: bool,
        configured_fields: list[str],
    ) -> dict[str, Any]:
        if not include_campaign_context:
            return {}

        base = payload.get("campaign")
        if not isinstance(base, dict):
            base = {
                "id": payload.get("campaign_id"),
                "slug": payload.get("campaign_slug"),
                "name": payload.get("campaign_name"),
                "objective": payload.get("campaign_objective"),
                "audience": payload.get("campaign_audience"),
                "theme": payload.get("campaign_theme"),
                "status": payload.get("campaign_status"),
                "role": payload.get("campaign_role"),
                "start_date": payload.get("campaign_start_date"),
                "end_date": payload.get("campaign_end_date"),
            }

        fields = configured_fields or [
            "id",
            "slug",
            "name",
            "objective",
            "audience",
            "theme",
            "status",
            "role",
            "start_date",
            "end_date",
        ]
        return {
            field: base.get(field)
            for field in fields
            if base.get(field) not in (None, "", [])
        }

    def _campaign_context_text(self, campaign_context: dict[str, Any]) -> str:
        if not campaign_context:
            return ""
        labels = {
            "id": "Campaign ID",
            "slug": "Campaign Slug",
            "name": "Campaign Name",
            "objective": "Campaign Objective",
            "audience": "Campaign Audience",
            "theme": "Campaign Theme",
            "status": "Campaign Status",
            "role": "Campaign Role",
            "start_date": "Campaign Start Date",
            "end_date": "Campaign End Date",
        }
        lines = []
        for key, value in campaign_context.items():
            lines.append(f"- {labels.get(key, key.replace('_', ' ').title())}: {value}")
        return "\n".join(lines)

    def _extract_revenue_context(
        self,
        payload: dict[str, Any],
        *,
        include_revenue_context: bool,
        configured_fields: list[str],
    ) -> dict[str, Any]:
        if not include_revenue_context:
            return {}
        base = payload.get("revenue_context")
        if not isinstance(base, dict):
            return {}
        fields = configured_fields or [
            "playbook_slug",
            "playbook_type",
            "persona",
            "offer",
            "cta",
            "audience",
            "proof_points",
            "conversion_goal",
        ]
        return {
            field: base.get(field)
            for field in fields
            if base.get(field) not in (None, "", [])
        }

    def _revenue_context_text(self, revenue_context: dict[str, Any]) -> str:
        if not revenue_context:
            return ""
        return "\n".join(f"- {key.replace('_', ' ').title()}: {value}" for key, value in revenue_context.items())

    def _extract_market_signal_context(
        self,
        payload: dict[str, Any],
        *,
        include_market_signals: bool,
    ) -> dict[str, Any]:
        if not include_market_signals:
            return {}

        signal = payload.get("competitor")
        if not isinstance(signal, dict):
            signal = {
                "id": payload.get("competitor_signal_id"),
                "summary": payload.get("competitor_summary"),
                "signal_type": payload.get("competitor_signal_type"),
                "severity": payload.get("competitor_severity"),
                "reaction_angle": payload.get("competitor_reaction_angle"),
            }
        return {
            key: value
            for key, value in signal.items()
            if value not in (None, "", [])
        }

    def _market_signal_context_text(self, signal: dict[str, Any]) -> str:
        if not signal:
            return ""
        return "\n".join(f"- {key.replace('_', ' ').title()}: {value}" for key, value in signal.items())

    def _extract_lead_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        lead = payload.get("lead")
        if not isinstance(lead, dict):
            lead = {
                "id": payload.get("lead_account_id"),
                "name": payload.get("lead_name"),
                "stage": payload.get("lead_stage"),
                "priority": payload.get("lead_priority"),
            }
        return {
            key: value
            for key, value in lead.items()
            if value not in (None, "", [])
        }

    def _lead_context_text(self, lead_context: dict[str, Any]) -> str:
        if not lead_context:
            return ""
        return "\n".join(f"- {key.replace('_', ' ').title()}: {value}" for key, value in lead_context.items())

    def _extract_partner_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        partner = payload.get("partner")
        if not isinstance(partner, dict):
            partner = {
                "slug": payload.get("partner_slug"),
                "name": payload.get("partner_name"),
                "event_type": payload.get("source_event_type") or payload.get("event_type"),
                "event_id": payload.get("source_event_id") or payload.get("external_event_id"),
                "intake_source": payload.get("intake_source"),
            }
        return {
            key: value
            for key, value in partner.items()
            if value not in (None, "", [])
        }

    def _partner_context_text(self, partner_context: dict[str, Any]) -> str:
        if not partner_context:
            return ""
        return "\n".join(f"- {key.replace('_', ' ').title()}: {value}" for key, value in partner_context.items())

    def _extract_blog_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        blog = payload.get("blog_context")
        if not isinstance(blog, dict):
            return {}
        return {
            key: value
            for key, value in blog.items()
            if value not in (None, "", [])
        }

    def _blog_context_text(self, blog_context: dict[str, Any]) -> str:
        if not blog_context:
            return ""
        lines: list[str] = []
        for key, value in blog_context.items():
            if isinstance(value, list):
                rendered = ", ".join(str(item) for item in value)
            else:
                rendered = value
            lines.append(f"- {key.replace('_', ' ').title()}: {rendered}")
        return "\n".join(lines)
