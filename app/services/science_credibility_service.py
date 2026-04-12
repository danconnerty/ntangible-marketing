from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.brain import KnowledgeNode
from app.models.review import DraftVariant
from app.models.science import ScienceContentStatus, ScienceContentType
from app.models.workflow import Platform, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.brain_query import BrainQuery
from app.services.trigger_engine import TriggerEngine
from app.services.workflow_engine import WorkflowEngine


SCIENCE_TYPE_CONFIG = {
    ScienceContentType.ADVISOR_SPOTLIGHT.value: {
        "label": "Advisor Spotlight",
        "content_type": "thought_leadership",
        "pillar": "thought_leadership",
        "summary_prefix": "Advisor spotlight content focused on the science team.",
    },
    ScienceContentType.WHITE_PAPER_EXCERPT.value: {
        "label": "White Paper Excerpt",
        "content_type": "thought_leadership",
        "pillar": "client_proof",
        "summary_prefix": "White paper excerpt content pulled into a social-ready format.",
    },
    ScienceContentType.PEER_REVIEW_MILESTONE.value: {
        "label": "Peer Review Milestone",
        "content_type": "data_drop",
        "pillar": "client_proof",
        "summary_prefix": "Peer review milestone content for a credibility update.",
    },
}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or f"science-{uuid.uuid4().hex[:8]}"


class ScienceCredibilityService:
    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)
        self.trigger_engine = TriggerEngine(db)
        self.workflow_engine = WorkflowEngine(db)

    def list_dashboard(self) -> dict[str, Any]:
        nodes = self.bq.list_knowledge_by_kind("reference_content", limit=50)
        science_nodes = [n for n in nodes if (n.metadata_ or {}).get("record_type") == "science"]
        records = [self._serialize_node(n) for n in science_nodes]
        return {
            "records": records,
            "counts": {
                "total": len(records),
                "advisor_spotlights": sum(
                    1 for r in records if r["science_type"] == ScienceContentType.ADVISOR_SPOTLIGHT.value
                ),
                "white_paper_excerpts": sum(
                    1 for r in records if r["science_type"] == ScienceContentType.WHITE_PAPER_EXCERPT.value
                ),
                "peer_review_milestones": sum(
                    1 for r in records if r["science_type"] == ScienceContentType.PEER_REVIEW_MILESTONE.value
                ),
            },
        }

    def generate_science_content(
        self,
        science_type: str,
        *,
        platform: str = "linkedin",
        actor: str = "science",
        topic: str | None = None,
        audience: str | None = None,
        source_focus: str | None = None,
        source_notes: list[str] | None = None,
        advisor_name: str | None = None,
        white_paper_title: str | None = None,
        milestone_name: str | None = None,
    ) -> dict[str, Any]:
        config = SCIENCE_TYPE_CONFIG.get(science_type)
        if config is None:
            raise ValueError(f"Unknown science content type: {science_type}")

        workflow = self._resolve_workflow(science_type, platform)
        request_text = self._build_request_text(
            science_type=science_type,
            topic=topic,
            audience=audience,
            source_focus=source_focus,
            source_notes=source_notes or [],
            advisor_name=advisor_name,
            white_paper_title=white_paper_title,
            milestone_name=milestone_name,
        )
        trigger = self.trigger_engine.create_manual_request(request_text, workflow.id)
        trigger.source_payload = {
            **getattr(trigger, "source_payload", {}),
            "science_type": science_type,
            "science_context": {
                "topic": topic,
                "audience": audience,
                "source_focus": source_focus,
                "source_notes": source_notes or [],
                "advisor_name": advisor_name,
                "white_paper_title": white_paper_title,
                "milestone_name": milestone_name,
                "actor": actor,
            },
            "request": request_text,
        }
        job = self.workflow_engine.execute(trigger)
        draft = self._latest_draft_for_job(job.id)
        status = ScienceContentStatus.REVIEW_READY if job.status != "failed" else ScienceContentStatus.FAILED

        title = self._science_title(science_type, topic, advisor_name, white_paper_title, milestone_name)
        summary = self._science_summary(science_type, topic, audience, source_focus, white_paper_title, milestone_name)

        node = self.bq.create_knowledge_node(
            kind="reference_content",
            title=title,
            status=status.value,
            metadata={
                "record_type": "science",
                "science_type": science_type,
                "slug": _slugify(title),
                "platform": platform,
                "workflow_id": str(workflow.id),
                "workflow_slug": workflow.slug,
                "trigger_event_id": str(trigger.id),
                "content_job_id": str(getattr(job, "id", "")) if getattr(job, "id", None) else None,
                "draft_variant_id": str(draft.id) if draft else None,
                "summary": summary,
                "source_focus": source_focus,
                "source_notes": source_notes or [],
                "actor": actor,
                "advisor_name": advisor_name,
                "white_paper_title": white_paper_title,
                "milestone_name": milestone_name,
                "job_status": job.status,
            },
        )
        return self._serialize_node(node, draft=draft, job_status=job.status)

    def _science_title(
        self,
        science_type: str,
        topic: str | None,
        advisor_name: str | None,
        white_paper_title: str | None,
        milestone_name: str | None,
    ) -> str:
        if science_type == ScienceContentType.ADVISOR_SPOTLIGHT.value:
            return f"Advisor Spotlight: {advisor_name or topic or 'NTangible Science Team'}"
        if science_type == ScienceContentType.WHITE_PAPER_EXCERPT.value:
            return f"White Paper Excerpt: {white_paper_title or topic or 'Science Brief'}"
        return f"Peer Review Milestone: {milestone_name or topic or 'Validation Update'}"

    def _science_summary(
        self,
        science_type: str,
        topic: str | None,
        audience: str | None,
        source_focus: str | None,
        white_paper_title: str | None,
        milestone_name: str | None,
    ) -> str:
        prefix = SCIENCE_TYPE_CONFIG[science_type]["summary_prefix"]
        parts = [prefix]
        if topic:
            parts.append(f"Topic: {topic}.")
        if audience:
            parts.append(f"Audience: {audience}.")
        if source_focus:
            parts.append(f"Focus: {source_focus}.")
        if white_paper_title:
            parts.append(f"White paper: {white_paper_title}.")
        if milestone_name:
            parts.append(f"Milestone: {milestone_name}.")
        return " ".join(parts)

    def _build_request_text(
        self,
        *,
        science_type: str,
        topic: str | None,
        audience: str | None,
        source_focus: str | None,
        source_notes: list[str],
        advisor_name: str | None,
        white_paper_title: str | None,
        milestone_name: str | None,
    ) -> str:
        lines = [
            f"Science credibility content type: {science_type}",
            f"Target audience: {audience or 'NTangible decision makers'}",
        ]
        if topic:
            lines.append(f"Topic: {topic}")
        if source_focus:
            lines.append(f"Source focus: {source_focus}")
        if advisor_name:
            lines.append(f"Advisor spotlight subject: {advisor_name}")
        if white_paper_title:
            lines.append(f"White paper title: {white_paper_title}")
        if milestone_name:
            lines.append(f"Milestone: {milestone_name}")
        if source_notes:
            lines.append("Source notes:")
            lines.extend(f"- {note}" for note in source_notes)
        lines.append("Write a proof-led, non-corporate post that can be reviewed and published manually.")
        return "\n".join(lines)

    def _resolve_workflow(self, science_type: str, platform: str) -> Workflow:
        platform_enum = Platform(platform)
        slug = f"science-{science_type}-{platform_enum.value}"
        workflow = self.db.query(Workflow).filter(Workflow.slug == slug).first()
        if workflow:
            return workflow

        workflow = Workflow(
            id=uuid.uuid4(),
            name=f"Science {science_type.replace('_', ' ').title()} {platform_enum.value.title()}",
            slug=slug,
            description="Manual-first science credibility workflow.",
            mode=WorkflowMode.MANUAL,
            platform=platform_enum,
            content_type=SCIENCE_TYPE_CONFIG[science_type]["content_type"],
            enabled=True,
        )
        self.db.add(workflow)
        self.db.flush()

        version = WorkflowVersion(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            version_number=1,
            config=WorkflowVersionConfig(
                prompt={
                    "tone_notes": "Write with authority, clarity, and zero brand-speak.",
                    "system_prompt_additions": "Always treat science credibility as evidence-led thought leadership.",
                },
                routing={
                    "target_content_type": SCIENCE_TYPE_CONFIG[science_type]["content_type"],
                    "target_intent": "brand",
                    "target_pillar": SCIENCE_TYPE_CONFIG[science_type]["pillar"],
                },
            ).model_dump(),
            version_note="Bootstrapped science credibility workflow",
            author="system",
            is_active=True,
        )
        self.db.add(version)
        self.db.flush()
        workflow.active_version_id = version.id
        self.db.flush()
        return workflow

    def _latest_draft_for_job(self, job_id: uuid.UUID) -> DraftVariant | None:
        return (
            self.db.query(DraftVariant)
            .filter(DraftVariant.content_job_id == job_id)
            .order_by(DraftVariant.created_at.desc())
            .first()
        )

    def _serialize_node(
        self,
        node: KnowledgeNode,
        draft: DraftVariant | None = None,
        job_status: str | None = None,
    ) -> dict[str, Any]:
        meta = node.metadata_ or {}
        return {
            "id": str(node.id),
            "science_type": meta.get("science_type", ""),
            "status": node.status,
            "title": node.title,
            "slug": meta.get("slug", ""),
            "platform": meta.get("platform", ""),
            "workflow_slug": meta.get("workflow_slug"),
            "summary": meta.get("summary", ""),
            "source_focus": meta.get("source_focus"),
            "source_notes": meta.get("source_notes") or [],
            "metadata": {k: v for k, v in meta.items() if k not in ("record_type",)},
            "draft_id": str(draft.id) if draft else meta.get("draft_variant_id"),
            "job_status": job_status or meta.get("job_status"),
            "created_at": node.created_at.isoformat() if node.created_at else None,
        }
