from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.brain import KnowledgeNode
from app.models.review import DraftVariant
from app.models.workflow import Platform
from app.services.brain_query import BrainQuery
from app.services.trigger_engine import TriggerEngine
from app.services.workflow_engine import WorkflowEngine


@dataclass(frozen=True)
class RepurposingSourceInput:
    source_kind: str
    source_id: str
    title: str
    source_text: str
    source_platform: str
    source_url: str | None = None
    actor: str = "planner"
    channels: list[str] = field(default_factory=list)
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RepurposingWorkflowRequest:
    partner_slug: str
    event_type: str
    platform: Platform
    workflow_slug: str
    content_type: str
    pillar: str
    context: str
    dynamic_value_groups: list[list[str]] = field(default_factory=list)
    approval_tier: str = "tier_1"


class RepurposingService:
    DEFAULT_CHANNELS = ("x", "linkedin", "instagram", "newsletter", "blog")

    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)
        self.trigger_engine = TriggerEngine(db)
        self.workflow_engine = WorkflowEngine(db)

    def list_dashboard(self, limit: int = 50) -> dict[str, list[dict[str, Any]]]:
        sources = self.bq.list_knowledge_by_kind("reference_content", limit=limit)
        repurposing_sources = [
            s for s in sources if (s.metadata_ or {}).get("repurposing_role") == "source"
        ]
        derivatives = [
            s for s in sources if (s.metadata_ or {}).get("repurposing_role") == "derivative"
        ]
        runs = self.bq.list_knowledge_by_kind("run", limit=limit)
        repurposing_runs = [r for r in runs if (r.metadata_ or {}).get("run_type") == "repurposing"]
        return {
            "sources": [self._serialize_source_node(s) for s in repurposing_sources],
            "derivatives": [self._serialize_derivative_node(d) for d in derivatives],
            "runs": [self._serialize_run_node(r) for r in repurposing_runs],
        }

    def fan_out_source(
        self,
        source: RepurposingSourceInput,
        *,
        channels: list[str] | None = None,
    ) -> dict[str, Any]:
        source_node = self._ensure_source(source)
        target_channels = self._resolve_channels(channels or source.channels)
        if not target_channels:
            target_channels = list(self.DEFAULT_CHANNELS)

        derivatives: list[dict[str, Any]] = []
        for channel in target_channels:
            if channel == "blog":
                derivative_node = self._build_blog_derivative_node(source, source_node.id)
                derivatives.append(self._serialize_derivative_node(derivative_node))
                continue

            workflow, job, draft = self._create_platform_derivative(source, source_node, channel)
            derivative_node = self.bq.create_knowledge_node(
                kind="reference_content",
                title=(
                    draft.compliance_result.get("subject")
                    if channel == "newsletter" and isinstance(draft.compliance_result, dict)
                    else f"{source.title} - {channel}"
                ),
                content=draft.content,
                status=draft.state.value,
                metadata={
                    "repurposing_role": "derivative",
                    "source_node_id": str(source_node.id),
                    "channel": channel,
                    "derivative_order": len(derivatives),
                    "source_platforms": [source.source_platform],
                    "is_blog_draft": False,
                    "workflow_id": str(workflow.id),
                    "workflow_slug": workflow.slug,
                    "content_job_id": str(job.id),
                    "draft_id": str(draft.id),
                },
            )
            derivatives.append(self._serialize_derivative_node(derivative_node))

        run_node = self.bq.create_knowledge_node(
            kind="run",
            title=f"Repurposing run: {source.title}",
            status="completed",
            metadata={
                "run_type": "repurposing",
                "source_node_id": str(source_node.id),
                "actor": source.actor,
                "channels": target_channels,
                "derivative_count": len(derivatives),
                "summary": {
                    "source_id": source.source_id,
                    "source_kind": source.source_kind,
                    "channels": target_channels,
                    "derivative_count": len(derivatives),
                },
            },
        )
        return {
            "source_id": str(source_node.id),
            "source_kind": source.source_kind,
            "source_title": source.title,
            "derivatives": derivatives,
            "run_id": str(run_node.id),
        }

    def repurpose_draft(self, source_draft_id: str, target_platforms: list[str] | None = None) -> list[dict[str, Any]]:
        draft = self._get_draft(source_draft_id)
        if draft is None:
            raise ValueError(f"Draft not found: {source_draft_id}")

        source = RepurposingSourceInput(
            source_kind="draft",
            source_id=str(source_draft_id),
            title=self._draft_title(draft),
            source_text=draft.content,
            source_platform=getattr(getattr(draft, "platform", None), "value", "linkedin"),
            source_url=getattr(draft, "post_url", None),
            actor="repurposer",
            channels=target_platforms or list(self.DEFAULT_CHANNELS),
            source_metadata={
                "draft_id": str(source_draft_id),
                "content_job_id": str(getattr(draft, "content_job_id", "")),
            },
        )
        return self.fan_out_source(source, channels=target_platforms)["derivatives"]

    def flag_for_recycling(self, draft_id: str, score: int) -> bool:
        if score < 75:
            return False

        draft = self._get_draft(draft_id)
        if draft is None:
            return False

        self.bq.create_knowledge_node(
            kind="reference_content",
            title=self._draft_title(draft),
            status="active",
            metadata={
                "repurposing_role": "source",
                "source_kind": "recycle_flag",
                "source_id": str(draft_id),
                "channel": getattr(getattr(draft, "platform", None), "value", "linkedin"),
                "source_url": getattr(draft, "post_url", None),
                "content_score": score,
                "recycle_recommended": True,
            },
        )
        return True

    def get_evergreen_candidates(self, min_age_days: int = 90, min_score: int = 75) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
        candidates: list[dict[str, Any]] = []
        for draft in self._query_all(DraftVariant, limit=1000):
            published_at = getattr(draft, "published_at", None) or getattr(draft, "created_at", None)
            if published_at is None or published_at > cutoff:
                continue
            compliance = draft.compliance_result or {}
            score = self._draft_score(draft, compliance)
            if score < min_score:
                continue
            candidates.append(
                {
                    "draft_id": str(draft.id),
                    "content_preview": draft.content[:240],
                    "content_score": score,
                    "score_label": compliance.get("score_label") or ("excellent" if score >= 90 else "strong"),
                    "published_at": published_at.isoformat() if hasattr(published_at, "isoformat") else None,
                    "platform": getattr(getattr(draft, "platform", None), "value", None),
                }
            )
        candidates.sort(key=lambda item: item["content_score"], reverse=True)
        return candidates

    def _ensure_source(self, source: RepurposingSourceInput) -> KnowledgeNode:
        existing_nodes = self.bq.list_knowledge_by_kind("reference_content", limit=500)
        for node in existing_nodes:
            meta = node.metadata_ or {}
            if (
                meta.get("repurposing_role") == "source"
                and meta.get("source_kind") == source.source_kind
                and meta.get("source_id") == source.source_id
            ):
                # Update in place
                node.title = source.title
                node.content = source.source_text
                node.metadata_ = {
                    **meta,
                    "channel": source.source_platform,
                    "source_url": source.source_url,
                    "source_metadata": source.source_metadata,
                }
                self.db.flush()
                return node

        return self.bq.create_knowledge_node(
            kind="reference_content",
            title=source.title,
            content=source.source_text,
            metadata={
                "repurposing_role": "source",
                "source_kind": source.source_kind,
                "source_id": source.source_id,
                "channel": source.source_platform,
                "source_url": source.source_url,
                "source_metadata": source.source_metadata,
            },
        )

    def _create_platform_derivative(
        self,
        source: RepurposingSourceInput,
        source_node: KnowledgeNode,
        channel: str,
    ):
        request = self._build_workflow_request(source, channel)
        workflow, _version = self.trigger_engine.ensure_workflow(request)
        trigger = self.trigger_engine.create_manual_request(request.context, workflow.id)
        trigger.source_payload = {
            **trigger.source_payload,
            "repurposing": {
                "source_kind": source.source_kind,
                "source_id": source.source_id,
                "source_title": source.title,
                "source_platform": source.source_platform,
                "channel": channel,
            },
            "request": request.context,
        }
        job = self.workflow_engine.execute(trigger)
        draft = self._first_draft_for_job(job.id)
        if draft is None:
            raise ValueError(f"No draft created for repurposing channel: {channel}")
        return workflow, job, draft

    def _build_workflow_request(self, source: RepurposingSourceInput, channel: str) -> RepurposingWorkflowRequest:
        platform = Platform(channel)
        content_type, pillar = self._channel_profile(channel)
        context = self._build_context(source, channel)
        return RepurposingWorkflowRequest(
            partner_slug="repurposing",
            event_type="content_repurpose",
            platform=platform,
            workflow_slug=f"repurpose-{channel}-{source.source_kind}-{source.source_id}".replace("_", "-"),
            content_type=content_type,
            pillar=pillar,
            context=context,
            dynamic_value_groups=[[source.title], [channel], [source.source_platform]],
            approval_tier="tier_1",
        )

    def _channel_profile(self, channel: str) -> tuple[str, str]:
        if channel == "x":
            return "trend_jack", "thought_leadership"
        if channel == "linkedin":
            return "company_update", "thought_leadership"
        if channel == "instagram":
            return "stat_card", "client_proof"
        if channel == "newsletter":
            return "newsletter", "client_proof"
        raise ValueError(f"Unsupported repurposing channel: {channel}")

    def _build_context(self, source: RepurposingSourceInput, channel: str) -> str:
        base = [
            f"Repurpose the following nucleus for {channel}.",
            f"Source title: {source.title}.",
            f"Source platform: {source.source_platform}.",
            f"Source text: {source.source_text}.",
            "Keep the angle faithful to the original but rewritten for the destination channel.",
        ]
        if source.source_url:
            base.append(f"Source URL: {source.source_url}.")
        if source.source_metadata:
            base.append(f"Source metadata: {source.source_metadata}.")
        if channel == "x":
            base.append("Make it punchy and concise.")
        elif channel == "linkedin":
            base.append("Use short paragraphs and a founder-led tone.")
        elif channel == "instagram":
            base.append("Make it visual-first and hooky.")
        elif channel == "newsletter":
            base.append("Write for a digest audience with a clear proof point and CTA.")
        return " ".join(base)

    def _build_blog_derivative_node(self, source: RepurposingSourceInput, source_node_id: uuid.UUID) -> KnowledgeNode:
        outline = self._build_blog_outline(source)
        return self.bq.create_knowledge_node(
            kind="reference_content",
            title=f"{source.title} - Blog Draft",
            content=outline,
            status="drafted",
            metadata={
                "repurposing_role": "derivative",
                "source_node_id": str(source_node_id),
                "channel": "blog",
                "derivative_order": 99,
                "source_platforms": [source.source_platform],
                "is_blog_draft": True,
                "source_kind": source.source_kind,
                "source_id": source.source_id,
                "seo_keywords": self._blog_keywords(source),
            },
        )

    def _build_blog_outline(self, source: RepurposingSourceInput) -> str:
        keywords = ", ".join(self._blog_keywords(source))
        return (
            f"# {source.title}\n\n"
            "## Why it matters\n"
            f"{source.source_text}\n\n"
            "## Key takeaways\n"
            "- Lead with the core tension.\n"
            "- Use one proof point per section.\n"
            "- Keep the CTA specific.\n\n"
            "## Suggested SEO keywords\n"
            f"{keywords}\n"
        )

    def _blog_keywords(self, source: RepurposingSourceInput) -> list[str]:
        return [
            source.title.lower(),
            f"{source.source_platform} insights",
            "sports performance assessment",
            "pressure performance",
        ]

    def _resolve_channels(self, channels: list[str]) -> list[str]:
        resolved: list[str] = []
        for channel in channels:
            channel = channel.lower().strip()
            if channel in self.DEFAULT_CHANNELS and channel not in resolved:
                resolved.append(channel)
        return resolved

    def _first_draft_for_job(self, content_job_id: uuid.UUID):
        try:
            return (
                self.db.query(DraftVariant)
                .filter(DraftVariant.content_job_id == content_job_id)
                .order_by(DraftVariant.created_at.asc())
                .first()
            )
        except Exception:
            return None

    def _get_draft(self, draft_id: str):
        try:
            import uuid as uuidlib

            draft_uuid = uuidlib.UUID(str(draft_id))
        except ValueError:
            return None
        try:
            return self.db.query(DraftVariant).filter(DraftVariant.id == draft_uuid).first()
        except Exception:
            return None

    def _draft_title(self, draft) -> str:
        compliance = draft.compliance_result or {}
        return compliance.get("subject") or getattr(draft, "title", None) or draft.content[:80]

    def _draft_score(self, draft, compliance: dict[str, Any]) -> float:
        if isinstance(compliance, dict):
            for key in ("content_score", "score"):
                value = compliance.get(key)
                if isinstance(value, (int, float)):
                    return float(value)
        return 0.0

    def _query_all(self, model, limit: int) -> list[Any]:
        try:
            return (
                self.db.query(model)
                .order_by(model.created_at.desc())
                .limit(limit)
                .all()
            )
        except Exception:
            return []

    def _serialize_source_node(self, node: KnowledgeNode) -> dict[str, Any]:
        meta = node.metadata_ or {}
        return {
            "id": str(node.id),
            "source_kind": meta.get("source_kind", ""),
            "source_id": meta.get("source_id", ""),
            "title": node.title,
            "channel": meta.get("channel", ""),
            "source_url": meta.get("source_url"),
            "source_text": node.content or "",
            "metadata": meta.get("source_metadata") or {},
        }

    def _serialize_derivative_node(self, node: KnowledgeNode) -> dict[str, Any]:
        meta = node.metadata_ or {}
        return {
            "id": str(node.id),
            "source_id": meta.get("source_node_id", ""),
            "channel": meta.get("channel", ""),
            "title": node.title,
            "content": node.content or "",
            "status": node.status,
            "derivative_order": meta.get("derivative_order", 0),
            "source_platforms": meta.get("source_platforms") or [],
            "metadata": {k: v for k, v in meta.items() if k not in ("repurposing_role", "source_node_id")},
            "is_blog_draft": meta.get("is_blog_draft", False),
        }

    def _serialize_run_node(self, node: KnowledgeNode) -> dict[str, Any]:
        meta = node.metadata_ or {}
        return {
            "id": str(node.id),
            "source_id": meta.get("source_node_id", ""),
            "actor": meta.get("actor", ""),
            "status": node.status,
            "derivative_count": meta.get("derivative_count", 0),
            "summary": meta.get("summary") or {},
        }
