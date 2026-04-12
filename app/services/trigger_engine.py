import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.review import ContentJob, DraftVariant
from app.models.trigger import (
    CalendarRule,
    PartnerSource,
    PartnerSourceType,
    TriggerEvent,
    TriggerProcessingStatus,
    TriggerType,
)
from app.models.workflow import DraftState, Platform, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.workflow_engine import WorkflowEngine


class TriggerEngine:
    def __init__(self, db: Session):
        self.db = db

    def fire_calendar_rule(self, rule: CalendarRule) -> TriggerEvent:
        fired_at = datetime.now(timezone.utc)
        event = TriggerEvent(
            trigger_type=TriggerType.CALENDAR,
            workflow_id=rule.workflow_id,
            calendar_rule_id=rule.id,
            processing_status=TriggerProcessingStatus.PROCESSED,
            source_payload={
                "rule_id": str(rule.id),
                "cron_expression": rule.cron_expression,
                "fired_at": fired_at.isoformat(),
                "timezone": rule.timezone,
                "publish_hour_local": rule.publish_hour_local,
                "publish_minute_local": rule.publish_minute_local,
                "all_day_generation": rule.all_day_generation,
            },
        )
        self.db.add(event)
        self.db.flush()
        return event

    def ingest_external(self, payload: dict, workflow_id: uuid.UUID) -> TriggerEvent:
        event = TriggerEvent(
            trigger_type=TriggerType.EXTERNAL,
            workflow_id=workflow_id,
            processing_status=TriggerProcessingStatus.RECEIVED,
            source_payload=payload,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def create_manual_request(self, request_text: str, workflow_id: uuid.UUID) -> TriggerEvent:
        event = TriggerEvent(
            trigger_type=TriggerType.MANUAL_REQUEST,
            workflow_id=workflow_id,
            processing_status=TriggerProcessingStatus.PROCESSED,
            source_payload={"request": request_text},
        )
        self.db.add(event)
        self.db.flush()
        return event

    def ensure_partner_source(self, partner_slug: str) -> PartnerSource:
        source = self.db.query(PartnerSource).filter(PartnerSource.slug == partner_slug).first()
        if source is not None:
            return source

        source = PartnerSource(
            id=uuid.uuid4(),
            slug=partner_slug,
            display_name=partner_slug.replace("_", " ").replace("-", " ").title(),
            source_type=PartnerSourceType.WEBHOOK,
            enabled=True,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def ensure_workflow(self, request) -> tuple[Workflow, WorkflowVersion]:
        workflow = self.db.query(Workflow).filter(Workflow.slug == request.workflow_slug).first()
        if workflow is not None and workflow.active_version_id is not None:
            version = (
                self.db.query(WorkflowVersion)
                .filter(WorkflowVersion.id == workflow.active_version_id)
                .first()
            )
            if version is not None:
                return workflow, version

        if workflow is None:
            workflow = Workflow(
                id=uuid.uuid4(),
                name=f"{request.partner_slug} {request.event_type} {request.platform.value}",
                slug=request.workflow_slug,
                description=f"Auto-generated partner workflow for {request.event_type}",
                mode=WorkflowMode.MANUAL,
                platform=request.platform,
                content_type=request.content_type,
                enabled=True,
            )
            self.db.add(workflow)
            self.db.commit()
            self.db.refresh(workflow)

        latest_version = (
            self.db.query(WorkflowVersion)
            .filter(WorkflowVersion.workflow_id == workflow.id)
            .order_by(WorkflowVersion.version_number.desc())
            .first()
        )
        version = WorkflowVersion(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            version_number=1 if latest_version is None else latest_version.version_number + 1,
            config=WorkflowVersionConfig(
                routing={
                    "target_pillar": request.pillar,
                    "target_intent": "partner",
                    "target_content_type": request.content_type,
                }
            ).model_dump(),
            version_note="Phase 5 partner trigger bootstrap",
            author="system",
            is_active=True,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)

        workflow.active_version_id = version.id
        self.db.commit()
        self.db.refresh(workflow)
        return workflow, version

    def queue_state_for_workflow(self, workflow: Workflow) -> DraftState:
        if workflow.mode == WorkflowMode.AUTOMATIC:
            return DraftState.AUTOMATIC_READY
        return DraftState.MANUAL_READY

    def build_existing_summary(self, trigger_event: TriggerEvent, workflow: Workflow) -> dict:
        content_job = self.db.query(ContentJob).filter(ContentJob.trigger_event_id == trigger_event.id).first()
        draft = None
        if content_job is not None:
            draft = self.db.query(DraftVariant).filter(DraftVariant.content_job_id == content_job.id).first()
        return {
            "trigger_event_id": str(trigger_event.id),
            "platform": workflow.platform.value,
            "status": draft.state.value if draft is not None else trigger_event.processing_status.value,
            "workflow_slug": workflow.slug,
            "post_url": draft.post_url if draft is not None else None,
            "deduped": True,
        }

    def execute_partner_request(
        self,
        partner_source: PartnerSource,
        normalized_event,
        request,
        *,
        intake_source: str = "webhook",
    ) -> dict:
        workflow, version = self.ensure_workflow(request)
        dedupe_key = f"{partner_source.slug}:{normalized_event.external_event_id}:{workflow.slug}"
        existing = self.db.query(TriggerEvent).filter(TriggerEvent.dedupe_key == dedupe_key).first()
        if existing is not None:
            return self.build_existing_summary(existing, workflow)

        trigger_event = TriggerEvent(
            id=uuid.uuid4(),
            trigger_type=TriggerType.EXTERNAL,
            workflow_id=workflow.id,
            partner_source_id=partner_source.id,
            external_event_type=normalized_event.event_type,
            external_event_id=normalized_event.external_event_id,
            processing_status=TriggerProcessingStatus.RECEIVED,
            dedupe_key=dedupe_key,
            source_payload=normalized_event.payload,
        )
        self.db.add(trigger_event)
        self.db.commit()
        self.db.refresh(trigger_event)

        try:
            trigger_event.source_payload = {
                **trigger_event.source_payload,
                "request": request.context,
                "dynamic_value_groups": request.dynamic_value_groups,
                "intent": "partner",
                "partner_slug": partner_source.slug,
                "partner_name": partner_source.display_name,
                "source_event_type": normalized_event.event_type,
                "source_event_id": normalized_event.external_event_id,
                "partner": {
                    "slug": partner_source.slug,
                    "name": partner_source.display_name,
                    "event_type": normalized_event.event_type,
                    "event_id": normalized_event.external_event_id,
                    "intake_source": intake_source,
                },
            }
            self.db.commit()
            workflow_job = WorkflowEngine(self.db).execute(trigger_event)
            self.db.commit()

            draft_variant = (
                self.db.query(DraftVariant)
                .filter(DraftVariant.content_job_id == workflow_job.id)
                .order_by(DraftVariant.created_at.asc())
                .first()
            )

            if draft_variant is None:
                trigger_event.processing_status = TriggerProcessingStatus.FAILED
                trigger_event.error_message = workflow_job.error_message or "Workflow produced no draft"
                self.db.commit()
                return {
                    "trigger_event_id": str(trigger_event.id),
                    "platform": request.platform.value,
                    "status": "failed",
                    "workflow_slug": workflow.slug,
                    "error": trigger_event.error_message,
                }

            if draft_variant.state == DraftState.FAILED:
                trigger_event.processing_status = TriggerProcessingStatus.FAILED
                trigger_event.error_message = draft_variant.failure_reason
            else:
                trigger_event.processing_status = TriggerProcessingStatus.PROCESSED
            self.db.commit()

            return {
                "trigger_event_id": str(trigger_event.id),
                "platform": request.platform.value,
                "status": draft_variant.state.value,
                "workflow_slug": workflow.slug,
                "post_url": draft_variant.post_url,
            }
        except ValueError as exc:
            trigger_event.processing_status = TriggerProcessingStatus.FAILED
            trigger_event.error_message = str(exc)
            self.db.commit()
            return {
                "trigger_event_id": str(trigger_event.id),
                "platform": request.platform.value,
                "status": "failed",
                "workflow_slug": workflow.slug,
                "error": str(exc),
            }

    def fire_schedule_rule(self, rule: "KnowledgeNode") -> "KnowledgeNode":
        """Fire a schedule_rule KnowledgeNode — creates a trigger KnowledgeNode."""
        from app.models.brain import KnowledgeNode
        from app.services.brain_query import BrainQuery
        bq = BrainQuery(self.db)
        fired_at = datetime.now(timezone.utc)
        meta = dict(rule.metadata_)
        trigger_node = bq.create_knowledge_node(
            kind="trigger",
            title=f"Schedule trigger: {rule.title}",
            status="active",
            confidence=1.0,
            trust_score=1.0,
            metadata={
                "trigger_type": "calendar",
                "rule_id": str(rule.id),
                "cron_expression": meta.get("cron_expression", ""),
                "fired_at": fired_at.isoformat(),
                "timezone": meta.get("timezone", "America/New_York"),
                "publish_hour_local": meta.get("publish_hour_local"),
                "publish_minute_local": meta.get("publish_minute_local"),
                "workflow_entity_id": meta.get("workflow_entity_id"),
            },
        )
        self.db.flush()
        return trigger_node

    def create_manual_trigger(self, request_text: str, workflow_entity_id: str) -> "KnowledgeNode":
        """Create a manual trigger KnowledgeNode."""
        from app.models.brain import KnowledgeNode
        from app.services.brain_query import BrainQuery
        bq = BrainQuery(self.db)
        trigger_node = bq.create_knowledge_node(
            kind="trigger",
            title=f"Manual trigger: {request_text[:60]}",
            status="active",
            confidence=1.0,
            trust_score=1.0,
            metadata={
                "trigger_type": "manual",
                "request": request_text,
                "workflow_entity_id": workflow_entity_id,
            },
        )
        self.db.flush()
        return trigger_node

    def list_events(self, limit: int = 50) -> list[dict]:
        events = self.db.query(TriggerEvent).order_by(TriggerEvent.created_at.desc()).limit(limit).all()
        summaries: list[dict] = []
        for event in events:
            workflow = self.db.query(Workflow).filter(Workflow.id == event.workflow_id).first()
            source = None
            if event.partner_source_id is not None:
                source = self.db.query(PartnerSource).filter(PartnerSource.id == event.partner_source_id).first()
            content_job = self.db.query(ContentJob).filter(ContentJob.trigger_event_id == event.id).first()
            draft = None
            if content_job is not None:
                draft = self.db.query(DraftVariant).filter(DraftVariant.content_job_id == content_job.id).first()
            summaries.append(
                {
                    "id": str(event.id),
                    "partner_slug": source.slug if source is not None else None,
                    "workflow_slug": workflow.slug if workflow is not None else None,
                    "platform": workflow.platform.value if workflow is not None else None,
                    "external_event_type": event.external_event_type,
                    "external_event_id": event.external_event_id,
                    "processing_status": event.processing_status.value,
                    "job_status": content_job.status if content_job is not None else None,
                    "draft_state": draft.state.value if draft is not None else None,
                    "post_url": draft.post_url if draft is not None else None,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                }
            )
        return summaries
