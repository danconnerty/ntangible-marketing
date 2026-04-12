from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.video_writer import VideoWriterAgent
from app.models.brain import KnowledgeNode
from app.models.review import DraftVariant
from app.models.trigger import TriggerEvent
from app.models.video import VideoBriefKind, VideoBriefStatus
from app.models.workflow import Platform, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.brain_query import BrainQuery
from app.services.trigger_engine import TriggerEngine
from app.services.workflow_engine import WorkflowEngine


class VideoContentService:
    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)
        self.agent = VideoWriterAgent()
        self.trigger_engine = TriggerEngine(db)
        self.workflow_engine = WorkflowEngine(db)

    def list_dashboard(self, limit: int = 50) -> dict[str, list[dict[str, Any]]]:
        briefs = self.bq.list_knowledge_by_kind("video_brief", limit=limit)
        return {
            "briefs": [self._serialize_brief_node(node) for node in briefs],
            "count": len(briefs),
        }

    def create_brief(
        self,
        *,
        kind: str,
        target_platform: str,
        context: str | None = None,
        source_material: str | None = None,
        source_mode: str = "manual",
        title: str | None = None,
        audience: str | None = None,
        cta: str | None = None,
    ) -> dict[str, Any]:
        kind_enum = VideoBriefKind(kind)
        platform_enum = Platform(target_platform)
        brief_data = self.agent.build_brief(
            kind=kind_enum.value,
            target_platform=platform_enum.value,
            context=context,
            source_mode=source_mode,
            title=title,
            audience=audience,
            cta=cta,
            source_material=source_material,
        )
        workflow = self._resolve_workflow(kind_enum, platform_enum, brief_data)
        trigger = self.trigger_engine.create_manual_request(brief_data["request_text"], workflow.id)
        trigger.source_payload = {
            **trigger.source_payload,
            "video_brief": brief_data,
            "video_kind": kind_enum.value,
            "video_platform": platform_enum.value,
            "video_source_mode": source_mode,
            "video_audience": audience,
        }
        self.db.flush()
        job = self.workflow_engine.execute(trigger)

        draft = self._latest_draft_for_job(job.id)
        status = VideoBriefStatus.BRIEFED if job.status == "completed" else VideoBriefStatus.NEEDS_REVIEW

        node = self.bq.create_knowledge_node(
            kind="video_brief",
            title=brief_data["title"],
            content=brief_data.get("script"),
            status=status.value,
            metadata={
                "kind": kind_enum.value,
                "platform": platform_enum.value,
                "brief_format": brief_data["brief_format"],
                "hook": brief_data["hook"],
                "thesis": brief_data["thesis"],
                "script": brief_data["script"],
                "shot_list": brief_data["shot_list"],
                "motion_graphic_notes": brief_data["motion_graphic_notes"],
                "caption": brief_data["caption"],
                "cta": brief_data["cta"],
                "estimated_duration_seconds": brief_data["estimated_duration_seconds"],
                "source_context": {
                    **brief_data["source_context"],
                    "workflow_slug": workflow.slug,
                    "job_status": job.status,
                },
                "workflow_id": str(workflow.id),
                "workflow_slug": workflow.slug,
                "trigger_event_id": str(trigger.id),
                "content_job_id": str(getattr(job, "id", "")) if getattr(job, "id", None) else None,
                "draft_variant_id": str(draft.id) if draft else None,
                "job_status": job.status,
                "draft_state": getattr(draft, "state", None).value if draft and getattr(draft, "state", None) else None,
                "accepted_at": datetime.now(timezone.utc).isoformat() if job.status == "completed" else None,
            },
        )
        return self._serialize_brief_node(node, workflow=workflow, job_status=job.status, trigger=trigger, draft=draft)

    def create_brief_from_submission(
        self,
        *,
        athlete_name: str,
        score: int,
        score_tier: str,
        testimonial_text: str | None,
        target_platform: str = "instagram",
        parent_name: str | None = None,
        source_request_id: str | None = None,
    ) -> dict[str, Any]:
        context = "\n".join(
            filter(
                None,
                [
                    f"Athlete: {athlete_name}",
                    f"Score: {score}",
                    f"Score tier: {score_tier}",
                    f"Parent/guardian: {parent_name}" if parent_name else None,
                    f"Submission: {testimonial_text}" if testimonial_text else None,
                    f"Request ID: {source_request_id}" if source_request_id else None,
                ],
            )
        )
        return self.create_brief(
            kind=VideoBriefKind.TESTIMONIAL.value,
            target_platform=target_platform,
            context=context,
            source_material=testimonial_text,
            source_mode="ugc_submission",
            title=f"{athlete_name} testimonial video brief",
            audience="athletes and parents",
            cta="Watch the full testimonial.",
        )

    def _resolve_workflow(
        self,
        kind: VideoBriefKind,
        platform: Platform,
        brief_data: dict[str, Any],
    ) -> Workflow:
        slug = f"video-{kind.value}-{platform.value}"
        workflow = self.db.query(Workflow).filter(Workflow.slug == slug).first()
        if workflow is not None:
            return workflow

        workflow = Workflow(
            id=uuid.uuid4(),
            name=brief_data["title"],
            slug=slug,
            description="Manual-first video content brief routed through the control room.",
            mode=WorkflowMode.MANUAL,
            platform=platform,
            content_type="video_brief",
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
                    "tone_notes": "Write like a direct creative brief with clear on-camera direction.",
                    "system_prompt_additions": "Produce concise support copy for a founder video, reel, or testimonial asset.",
                },
                retrieval={
                    "include_campaign_context": True,
                    "include_market_signals": True,
                },
                routing={
                    "target_content_type": "video_brief",
                    "target_pillar": "thought_leadership" if kind == VideoBriefKind.FOUNDER_RAW else "client_proof",
                    "target_intent": "brand",
                },
            ).model_dump(),
            version_note="Bootstrapped video brief workflow",
            author="system",
            is_active=True,
        )
        self.db.add(version)
        self.db.flush()
        workflow.active_version_id = version.id
        self.db.flush()
        return workflow

    def _latest_draft_for_job(self, job_id: uuid.UUID | None) -> DraftVariant | None:
        if job_id is None:
            return None
        return (
            self.db.query(DraftVariant)
            .filter(DraftVariant.content_job_id == job_id)
            .order_by(DraftVariant.created_at.asc())
            .first()
        )

    def _serialize_brief_node(
        self,
        node: KnowledgeNode,
        *,
        workflow: Workflow | None = None,
        job_status: str | None = None,
        trigger: TriggerEvent | None = None,
        draft: DraftVariant | None = None,
    ) -> dict[str, Any]:
        meta = node.metadata_ or {}
        workflow_slug = meta.get("workflow_slug") or (workflow.slug if workflow else None)
        return {
            "id": str(node.id),
            "title": node.title,
            "kind": meta.get("kind", ""),
            "platform": meta.get("platform", ""),
            "brief_format": meta.get("brief_format", ""),
            "status": node.status,
            "hook": meta.get("hook", ""),
            "thesis": meta.get("thesis", ""),
            "script": meta.get("script", ""),
            "shot_list": meta.get("shot_list") or [],
            "motion_graphic_notes": meta.get("motion_graphic_notes"),
            "caption": meta.get("caption"),
            "cta": meta.get("cta"),
            "estimated_duration_seconds": meta.get("estimated_duration_seconds"),
            "source_context": meta.get("source_context") or {},
            "workflow_id": meta.get("workflow_id"),
            "workflow_slug": workflow_slug,
            "trigger_event_id": meta.get("trigger_event_id") or (str(trigger.id) if trigger else None),
            "content_job_id": meta.get("content_job_id"),
            "draft_variant_id": meta.get("draft_variant_id") or (str(draft.id) if draft else None),
            "job_status": job_status or meta.get("job_status"),
            "draft_state": meta.get("draft_state") or (
                getattr(draft, "state", None).value if draft and getattr(draft, "state", None) else None
            ),
            "trigger_type": (
                getattr(getattr(trigger, "trigger_type", None), "value", getattr(trigger, "trigger_type", None))
                if trigger
                else None
            ),
            "created_at": node.created_at.isoformat() if node.created_at else None,
        }
