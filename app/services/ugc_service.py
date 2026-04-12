from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.video_writer import VideoWriterAgent
from app.models.brain import KnowledgeNode
from app.models.workflow import Platform, Workflow, WorkflowMode, WorkflowVersion
from app.renderers.base import CanvaRenderRequest
from app.renderers.canva_factory import get_canva_renderer
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.brain_query import BrainQuery
from app.services.trigger_engine import TriggerEngine
from app.services.video_content_service import VideoContentService
from app.services.workflow_engine import WorkflowEngine


class UGCService:
    MIN_TESTIMONIAL_SCORE = 750

    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)
        self.agent = VideoWriterAgent()
        self.trigger_engine = TriggerEngine(db)
        self.workflow_engine = WorkflowEngine(db)
        self.video_service = VideoContentService(db)

    def list_dashboard(self, limit: int = 50) -> dict[str, Any]:
        outreach_nodes = self.bq.list_knowledge_by_kind("outreach", limit=limit)
        submission_nodes = self.bq.list_knowledge_by_kind("submission", limit=limit)
        return {
            "requests": [self._serialize_request_node(node) for node in outreach_nodes],
            "submissions": [self._serialize_submission_node(node) for node in submission_nodes],
            "request_count": len(outreach_nodes),
            "submission_count": len(submission_nodes),
        }

    def create_testimonial_request(
        self,
        *,
        athlete_name: str,
        score: int,
        athlete_email: str | None = None,
        parent_name: str | None = None,
        parent_email: str | None = None,
        score_tier: str | None = None,
        athlete_age: int | None = None,
        sport: str | None = None,
        context: str | None = None,
        source_partner: str | None = None,
    ) -> dict[str, Any]:
        if score < self.MIN_TESTIMONIAL_SCORE:
            raise ValueError(f"Testimonial requests require a score of at least {self.MIN_TESTIMONIAL_SCORE}")

        resolved_tier = score_tier or self._score_tier(score)
        request_payload = self.agent.build_testimonial_request(
            athlete_name=athlete_name,
            athlete_email=athlete_email,
            parent_name=parent_name,
            parent_email=parent_email,
            score=score,
            score_tier=resolved_tier,
            sport=sport,
        )
        graphic = self._render_score_graphic(
            athlete_name=athlete_name,
            score=score,
            score_tier=resolved_tier,
            sport=sport,
        )
        workflow = self._resolve_request_workflow()
        request_context = self._build_request_context(
            athlete_name=athlete_name,
            score=score,
            score_tier=resolved_tier,
            sport=sport,
            context=context,
            source_partner=source_partner,
        )
        trigger = self.trigger_engine.create_manual_request(request_context, workflow.id)
        trigger.source_payload = {
            **getattr(trigger, "source_payload", {}),
            "ugc_request": {
                "athlete_name": athlete_name,
                "score": score,
                "score_tier": resolved_tier,
                "sport": sport,
                "source_partner": source_partner,
                "context": context,
            },
            "request": request_context,
        }
        job = self.workflow_engine.execute(trigger)

        job_status = getattr(job, "status", None)
        status = "sent" if job_status in {"completed", "manual_ready"} else "draft"

        node = self.bq.create_knowledge_node(
            kind="outreach",
            title=f"UGC testimonial request: {athlete_name}",
            content=request_payload.get("request_copy"),
            status=status,
            metadata={
                "athlete_name": athlete_name,
                "athlete_email": athlete_email,
                "parent_name": parent_name,
                "parent_email": parent_email,
                "score": score,
                "score_tier": resolved_tier,
                "subject": request_payload["subject"],
                "preview_text": request_payload["preview_text"],
                "request_copy": request_payload["request_copy"],
                "graphic_path": graphic.get("graphic_path"),
                "graphic_url": graphic.get("graphic_url"),
                "workflow_id": str(workflow.id),
                "workflow_slug": workflow.slug,
                "trigger_event_id": str(getattr(trigger, "id", "")),
                "content_job_id": str(getattr(job, "id", "")) if getattr(job, "id", None) else None,
                "video_brief_id": None,
                "source_context": {
                    "athlete_age": athlete_age,
                    "sport": sport,
                    "context": context,
                    "source_partner": source_partner,
                    "workflow_slug": workflow.slug,
                    "job_status": job_status,
                },
            },
        )
        return self._serialize_request_node(node, workflow_slug=workflow.slug)

    def submit_testimonial(
        self,
        *,
        athlete_name: str,
        score: int,
        video_url: str,
        testimonial_text: str | None = None,
        athlete_email: str | None = None,
        parent_name: str | None = None,
        parent_email: str | None = None,
        athlete_age: int | None = None,
        consent_athlete: bool = True,
        consent_parent: bool = False,
        consent_share: bool = True,
        score_tier: str | None = None,
        request_id: str | None = None,
        source_partner: str | None = None,
        context: str | None = None,
    ) -> dict[str, Any]:
        if not consent_athlete:
            raise ValueError("Athlete consent is required")
        if athlete_age is not None and athlete_age < 18 and not consent_parent:
            raise ValueError("Parent consent is required for minors")

        resolved_tier = score_tier or self._score_tier(score)
        graphic = self._render_score_graphic(
            athlete_name=athlete_name,
            score=score,
            score_tier=resolved_tier,
            sport=None,
        )
        workflow = self._resolve_submission_workflow()
        submission_context = self._build_submission_context(
            athlete_name=athlete_name,
            score=score,
            score_tier=resolved_tier,
            testimonial_text=testimonial_text,
            context=context,
            source_partner=source_partner,
            video_url=video_url,
        )
        trigger = self.trigger_engine.create_manual_request(submission_context, workflow.id)
        trigger.source_payload = {
            **getattr(trigger, "source_payload", {}),
            "ugc_submission": {
                "athlete_name": athlete_name,
                "score": score,
                "score_tier": resolved_tier,
                "video_url": video_url,
                "source_partner": source_partner,
                "request_id": request_id,
                "context": context,
            },
            "request": submission_context,
        }
        job = self.workflow_engine.execute(trigger)

        video_brief: dict[str, Any] | None = None
        if score >= self.MIN_TESTIMONIAL_SCORE and consent_share:
            video_brief = self.video_service.create_brief_from_submission(
                athlete_name=athlete_name,
                score=score,
                score_tier=resolved_tier,
                testimonial_text=testimonial_text,
                target_platform="instagram",
                parent_name=parent_name,
                source_request_id=request_id,
            )

        job_status = getattr(job, "status", None)
        status = "accepted" if job_status in {"completed", "manual_ready"} else "needs_review"

        node = self.bq.create_knowledge_node(
            kind="submission",
            title=f"UGC submission: {athlete_name}",
            content=testimonial_text,
            status=status,
            metadata={
                "request_id": request_id,
                "athlete_name": athlete_name,
                "athlete_email": athlete_email,
                "parent_name": parent_name,
                "parent_email": parent_email,
                "athlete_age": athlete_age,
                "consent_athlete": consent_athlete,
                "consent_parent": consent_parent,
                "consent_share": consent_share,
                "score": score,
                "score_tier": resolved_tier,
                "video_url": video_url,
                "testimonial_text": testimonial_text,
                "shareable_score_public": consent_share,
                "graphic_path": graphic.get("graphic_path"),
                "graphic_url": graphic.get("graphic_url"),
                "workflow_id": str(workflow.id),
                "workflow_slug": workflow.slug,
                "trigger_event_id": str(getattr(trigger, "id", "")),
                "content_job_id": str(getattr(job, "id", "")) if getattr(job, "id", None) else None,
                "video_brief_id": video_brief.get("id") if video_brief else None,
                "video_brief": video_brief,
                "source_context": {
                    "context": context,
                    "source_partner": source_partner,
                    "request_id": request_id,
                    "workflow_slug": workflow.slug,
                    "job_status": job_status,
                },
                "accepted_at": datetime.now(timezone.utc).isoformat() if job_status in {"completed", "manual_ready"} else None,
            },
        )
        return self._serialize_submission_node(node, workflow_slug=workflow.slug, video_brief=video_brief)

    def _render_score_graphic(
        self,
        *,
        athlete_name: str,
        score: int,
        score_tier: str,
        sport: str | None,
    ) -> dict[str, str | None]:
        render_result = get_canva_renderer().render(
            CanvaRenderRequest(
                template_family="ugc_score_graphic",
                brand_mode="ntangible",
                canva_template_id="ugc_score_graphic",
                text_fields={
                    "athlete_name": athlete_name,
                    "score_tier": score_tier,
                    "sport": sport or "athlete",
                },
                numeric_fields={"score": score},
                image_references=[],
                output_asset_roles=["primary"],
                title=f"{athlete_name} score graphic",
            )
        )
        asset = render_result.assets[0] if render_result.assets else None
        return {
            "graphic_path": getattr(asset, "storage_path", None),
            "graphic_url": getattr(asset, "url", None),
        }

    def _resolve_request_workflow(self) -> Workflow:
        return self._resolve_workflow(
            slug="ugc-testimonial-request-newsletter",
            name="UGC Testimonial Request",
            platform=Platform.NEWSLETTER,
            content_type="newsletter",
            pillar="client_proof",
            system_prompt="Create an athlete testimonial request that is warm, consent-aware, and specific.",
        )

    def _resolve_submission_workflow(self) -> Workflow:
        return self._resolve_workflow(
            slug="ugc-testimonial-submission-instagram",
            name="UGC Testimonial Submission",
            platform=Platform.INSTAGRAM,
            content_type="partner_content",
            pillar="client_proof",
            system_prompt="Turn a consented athlete testimonial into a reusable proof asset workflow.",
        )

    def _resolve_workflow(
        self,
        *,
        slug: str,
        name: str,
        platform: Platform,
        content_type: str,
        pillar: str,
        system_prompt: str,
    ) -> Workflow:
        workflow = self.db.query(Workflow).filter(Workflow.slug == slug).first()
        if workflow is not None:
            return workflow

        workflow = Workflow(
            id=uuid.uuid4(),
            name=name,
            slug=slug,
            description="Manual-first UGC workflow routed through the control room.",
            mode=WorkflowMode.MANUAL,
            platform=platform,
            content_type=content_type,
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
                    "tone_notes": "Write like a direct operator who respects consent and clarity.",
                    "system_prompt_additions": system_prompt,
                },
                routing={
                    "target_content_type": content_type,
                    "target_intent": "brand",
                    "target_pillar": pillar,
                },
            ).model_dump(),
            version_note="Bootstrapped UGC workflow",
            author="system",
            is_active=True,
        )
        self.db.add(version)
        self.db.flush()
        workflow.active_version_id = version.id
        self.db.flush()
        return workflow

    def _score_tier(self, score: int) -> str:
        if score >= 900:
            return "Elite"
        if score >= 850:
            return "Gold"
        if score >= 800:
            return "Silver"
        if score >= 750:
            return "Certified"
        return "Developing"

    def _build_request_context(
        self,
        *,
        athlete_name: str,
        score: int,
        score_tier: str,
        sport: str | None,
        context: str | None,
        source_partner: str | None,
    ) -> str:
        parts = [
            f"Create a testimonial request for {athlete_name}.",
            f"Score: {score}.",
            f"Score tier: {score_tier}.",
            f"Sport: {sport}." if sport else "",
            f"Source partner: {source_partner}." if source_partner else "",
            f"Context: {context}." if context else "",
            "Keep it warm, consent-aware, and easy for a parent or athlete to act on.",
        ]
        return " ".join(part for part in parts if part)

    def _build_submission_context(
        self,
        *,
        athlete_name: str,
        score: int,
        score_tier: str,
        testimonial_text: str | None,
        context: str | None,
        source_partner: str | None,
        video_url: str,
    ) -> str:
        parts = [
            f"UGC submission from {athlete_name}.",
            f"Score: {score}.",
            f"Score tier: {score_tier}.",
            f"Video URL: {video_url}.",
            f"Testimonial: {testimonial_text}." if testimonial_text else "",
            f"Source partner: {source_partner}." if source_partner else "",
            f"Context: {context}." if context else "",
            "Route this into the manual-first proof workflow and prepare a video brief if it is reusable.",
        ]
        return " ".join(part for part in parts if part)

    def _serialize_request_node(
        self,
        node: KnowledgeNode,
        *,
        workflow_slug: str | None = None,
    ) -> dict[str, Any]:
        meta = node.metadata_ or {}
        source_context = meta.get("source_context") or {}
        return {
            "id": str(node.id),
            "athlete_name": meta.get("athlete_name"),
            "athlete_email": meta.get("athlete_email"),
            "parent_name": meta.get("parent_name"),
            "parent_email": meta.get("parent_email"),
            "score": meta.get("score"),
            "score_tier": meta.get("score_tier"),
            "subject": meta.get("subject"),
            "preview_text": meta.get("preview_text"),
            "request_copy": meta.get("request_copy"),
            "graphic_path": meta.get("graphic_path"),
            "graphic_url": meta.get("graphic_url"),
            "status": node.status,
            "workflow_id": meta.get("workflow_id"),
            "workflow_slug": workflow_slug or meta.get("workflow_slug"),
            "trigger_event_id": meta.get("trigger_event_id"),
            "content_job_id": meta.get("content_job_id"),
            "video_brief_id": meta.get("video_brief_id"),
            "source_context": source_context,
        }

    def _serialize_submission_node(
        self,
        node: KnowledgeNode,
        *,
        workflow_slug: str | None = None,
        video_brief: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta = node.metadata_ or {}
        source_context = meta.get("source_context") or {}
        brief_payload = video_brief or meta.get("video_brief")
        video_brief_id = meta.get("video_brief_id") or (brief_payload.get("id") if brief_payload else None)
        return {
            "id": str(node.id),
            "request_id": meta.get("request_id"),
            "athlete_name": meta.get("athlete_name"),
            "athlete_email": meta.get("athlete_email"),
            "parent_name": meta.get("parent_name"),
            "parent_email": meta.get("parent_email"),
            "athlete_age": meta.get("athlete_age"),
            "score": meta.get("score"),
            "score_tier": meta.get("score_tier"),
            "video_url": meta.get("video_url"),
            "testimonial_text": meta.get("testimonial_text"),
            "status": node.status,
            "consent_athlete": meta.get("consent_athlete"),
            "consent_parent": meta.get("consent_parent"),
            "consent_share": meta.get("consent_share"),
            "shareable_score_public": meta.get("shareable_score_public"),
            "graphic_path": meta.get("graphic_path"),
            "graphic_url": meta.get("graphic_url"),
            "workflow_id": meta.get("workflow_id"),
            "workflow_slug": workflow_slug or meta.get("workflow_slug"),
            "trigger_event_id": meta.get("trigger_event_id"),
            "content_job_id": meta.get("content_job_id"),
            "video_brief_id": video_brief_id,
            "video_brief": brief_payload,
            "source_context": source_context,
            "accepted_at": meta.get("accepted_at"),
        }
