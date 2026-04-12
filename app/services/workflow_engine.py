import logging
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.review import ContentJob, DraftVariant
from app.models.trigger import TriggerEvent, TriggerType
from app.models.workflow import DraftState, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.platform_generation import PlatformGenerationService
from app.services.prompt_assembler import PromptAssembler

logger = logging.getLogger(__name__)


def _end_of_day(tz_name: str) -> datetime:
    """Compute end of current day in the given timezone, returned as UTC."""
    try:
        tz = ZoneInfo(tz_name)
    except (ImportError, KeyError):
        tz = timezone.utc
    now_local = datetime.now(tz)
    end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=0)
    return end_local.astimezone(timezone.utc)


def _scheduled_publish_time(trigger: TriggerEvent, tz_name: str) -> datetime | None:
    if trigger.trigger_type != TriggerType.CALENDAR:
        return None

    hour = trigger.source_payload.get("publish_hour_local")
    if hour is None:
        return None
    minute = trigger.source_payload.get("publish_minute_local") or 0

    try:
        tz = ZoneInfo(tz_name)
    except (ImportError, KeyError):
        tz = timezone.utc

    fired_at_raw = trigger.source_payload.get("fired_at")
    fired_at = datetime.fromisoformat(fired_at_raw) if fired_at_raw else datetime.now(timezone.utc)
    local_fired = fired_at.astimezone(tz)
    scheduled_local = local_fired.replace(hour=hour, minute=minute, second=0, microsecond=0)
    scheduled_utc = scheduled_local.astimezone(timezone.utc)
    if scheduled_utc < fired_at:
        return fired_at
    return scheduled_utc


class WorkflowEngine:
    def __init__(self, db: Session):
        self.db = db

    def resolve_workflow(self, trigger: TriggerEvent) -> Workflow:
        """Look up the workflow for a trigger event."""
        workflow = self.db.query(Workflow).filter(
            Workflow.id == trigger.workflow_id,
            Workflow.enabled == True,
        ).first()
        if not workflow:
            raise ValueError(f"No enabled workflow found for id {trigger.workflow_id}")
        return workflow

    def get_active_version(self, workflow: Workflow) -> WorkflowVersion:
        """Get the active version for a workflow."""
        if workflow.active_version_id:
            version = self.db.query(WorkflowVersion).filter(
                WorkflowVersion.id == workflow.active_version_id,
            ).first()
            if version:
                return version
        # Fallback to highest version number
        version = self.db.query(WorkflowVersion).filter(
            WorkflowVersion.workflow_id == workflow.id,
        ).order_by(WorkflowVersion.version_number.desc()).first()
        if not version:
            raise ValueError(f"No versions found for workflow {workflow.slug}")
        return version

    def execute(self, trigger: TriggerEvent) -> ContentJob:
        """Resolve workflow, retrieve context, generate platform-specific drafts, and persist canonical records."""
        workflow = self.resolve_workflow(trigger)
        version = self.get_active_version(workflow)

        job = ContentJob(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            workflow_version_id=version.id,
            trigger_event_id=trigger.id,
            status="running",
        )
        self.db.add(job)
        self.db.flush()

        try:
            assembler = PromptAssembler(self.db)
            payload = assembler.assemble(workflow, version, trigger)
            job.prompt_snapshot = {
                "system": payload["system"],
                "user": payload["user"],
                "retrieved_examples": payload["retrieved_examples"],
                "campaign": payload.get("campaign") or {},
                "campaign_context": payload.get("campaign_context") or {},
                "revenue_context": payload.get("revenue_context") or {},
                "partner_context": payload.get("partner_context") or {},
                "market_signal_context": payload.get("market_signal_context") or {},
                "lead_context": payload.get("lead_context") or {},
            }
            job.retrieved_memory_ids = [
                uuid.UUID(memory_id)
                for memory_id in payload.get("retrieved_memory_ids", [])
                if memory_id
            ]

            config = WorkflowVersionConfig(**version.config)
            tz_name = trigger.source_payload.get("timezone") or workflow.timezone or "America/New_York"
            generated_candidates = PlatformGenerationService(self.db).generate(workflow, version, payload)
            compliance_results = []
            created_drafts = 0

            for candidate in generated_candidates:
                state, recommended_at, scheduled_at, expires_at = self._draft_timing(
                    workflow,
                    config,
                    tz_name,
                    trigger,
                )
                draft = DraftVariant(
                    id=uuid.uuid4(),
                    content_job_id=job.id,
                    platform=workflow.platform,
                    intent=trigger.source_payload.get("intent") or config.routing.target_intent or "brand",
                    partner_slug=trigger.source_payload.get("partner_slug"),
                    partner_name=trigger.source_payload.get("partner_name"),
                    source_event_type=trigger.source_payload.get("source_event_type") or trigger.source_payload.get("event_type"),
                    source_event_id=trigger.source_payload.get("source_event_id") or trigger.source_payload.get("external_event_id"),
                    content=candidate.content,
                    hashtags=candidate.hashtags,
                    state=state,
                    timezone=tz_name,
                    recommended_publish_at=recommended_at,
                    scheduled_publish_at=scheduled_at,
                    expires_at=expires_at,
                    compliance_result=candidate.compliance_result,
                    failure_reason=candidate.failure_reason,
                )
                self.db.add(draft)
                self.db.flush()
                created_drafts += 1
                compliance_results.append(candidate.compliance_result)

                for asset_payload in candidate.asset_payloads:
                    self.db.add(
                        Asset(
                            id=uuid.uuid4(),
                            draft_variant_id=draft.id,
                            workflow_id=workflow.id,
                            asset_type=asset_payload.asset_type,
                            asset_role=asset_payload.asset_role,
                            provider=asset_payload.provider,
                            render_status=asset_payload.render_status,
                            sort_order=asset_payload.sort_order,
                            filename=asset_payload.filename,
                            storage_path=asset_payload.storage_path,
                            url=asset_payload.url,
                            mime_type=asset_payload.mime_type,
                            platform_metadata=asset_payload.platform_metadata,
                        )
                    )

            job.compliance_snapshot = compliance_results
            job.status = "completed" if created_drafts else "failed"
            if created_drafts == 0:
                job.error_message = "No drafts were created"

        except Exception as exc:
            logger.error("Workflow execution failed: %s", exc)
            job.status = "failed"
            job.error_message = str(exc)

        self.db.flush()
        return job

    def execute_brain(self, trigger_node: "KnowledgeNode") -> "KnowledgeNode":
        """Brain-native execute: creates KnowledgeNode drafts linked via edges."""
        from app.models.brain import EntityNode, KnowledgeNode
        from app.services.brain_query import BrainQuery
        bq = BrainQuery(self.db)

        # Get workflow entity
        wf_id_str = trigger_node.metadata_.get("workflow_entity_id")
        if not wf_id_str:
            raise ValueError("Trigger has no workflow_entity_id")
        import uuid as _uuid
        workflow_entity = bq.get_entity(_uuid.UUID(wf_id_str))
        if workflow_entity is None:
            raise ValueError(f"Workflow entity {wf_id_str} not found")

        # Create job node
        job_node = bq.create_knowledge_node(
            kind="job",
            title=f"Job: {workflow_entity.canonical_name}",
            status="running",
            confidence=1.0,
            trust_score=1.0,
            metadata={
                "workflow_entity_id": wf_id_str,
                "trigger_id": str(trigger_node.id),
            },
        )
        bq.create_edge(
            source_id=trigger_node.id,
            target_id=job_node.id,
            source_type="knowledge",
            target_type="knowledge",
            relation="produced_job",
        )
        bq.create_edge(
            source_id=workflow_entity.id,
            target_id=job_node.id,
            source_type="entity",
            target_type="knowledge",
            relation="ran_job",
        )

        try:
            # Use existing Workflow/WorkflowVersion objects if they exist (transition compatibility)
            # Look up Workflow by slug from workflow_entity.slug
            from app.models.workflow import Workflow, WorkflowVersion
            workflow = self.db.query(Workflow).filter(Workflow.slug == workflow_entity.slug).first()
            if workflow is None:
                # Create a minimal stub for PromptAssembler compatibility
                job_meta = dict(job_node.metadata_)
                job_meta["error"] = "No legacy workflow found for brain execute"
                job_node.metadata_ = job_meta
                job_node.status = "failed"
                self.db.flush()
                return job_node

            version = self.get_active_version(workflow)

            # Build a TriggerEvent-like payload for PromptAssembler
            from app.models.trigger import TriggerEvent, TriggerType, TriggerProcessingStatus
            trigger_meta = trigger_node.metadata_
            stub_trigger = TriggerEvent(
                id=trigger_node.id,
                trigger_type=TriggerType.CALENDAR if trigger_meta.get("trigger_type") == "calendar" else TriggerType.MANUAL_REQUEST,
                workflow_id=workflow.id,
                processing_status=TriggerProcessingStatus.PROCESSED,
                source_payload={
                    "fired_at": trigger_meta.get("fired_at"),
                    "timezone": trigger_meta.get("timezone", workflow.timezone),
                    "publish_hour_local": trigger_meta.get("publish_hour_local"),
                    "publish_minute_local": trigger_meta.get("publish_minute_local"),
                    "request": trigger_meta.get("request", ""),
                },
            )

            assembler = PromptAssembler(self.db)
            payload = assembler.assemble(workflow, version, stub_trigger)

            config = WorkflowVersionConfig(**version.config)
            tz_name = trigger_meta.get("timezone") or workflow.timezone or "America/New_York"
            generated_candidates = PlatformGenerationService(self.db).generate(workflow, version, payload)

            created_drafts = 0
            for candidate in generated_candidates:
                draft_node = bq.create_draft(
                    title=f"{workflow.platform.value} draft: {candidate.content[:60]}",
                    content=candidate.content,
                    platform=workflow.platform.value,
                    intent="brand",
                    pillar=config.routing.target_pillar or "thought_leadership",
                    hashtags=list(candidate.hashtags or []),
                    mode=workflow.mode.value,
                    status="review_required" if workflow.mode.value == "manual" else "scheduled",
                    confidence=0.8,
                    trust_score=0.8,
                    extra_metadata={
                        "compliance_result": candidate.compliance_result,
                        "failure_reason": candidate.failure_reason,
                    },
                )
                bq.create_edge(
                    source_id=workflow_entity.id,
                    target_id=draft_node.id,
                    source_type="entity",
                    target_type="knowledge",
                    relation="produced",
                )
                bq.create_edge(
                    source_id=job_node.id,
                    target_id=draft_node.id,
                    source_type="knowledge",
                    target_type="knowledge",
                    relation="produced_draft",
                )
                created_drafts += 1

            job_meta = dict(job_node.metadata_)
            job_meta["drafts_created"] = created_drafts
            job_node.metadata_ = job_meta
            job_node.status = "completed" if created_drafts else "failed"
            if created_drafts == 0:
                job_meta["error"] = "No drafts were created"
                job_node.metadata_ = job_meta

        except Exception as exc:
            logger.error("Brain workflow execution failed: %s", exc)
            job_meta = dict(job_node.metadata_)
            job_meta["error"] = str(exc)
            job_node.metadata_ = job_meta
            job_node.status = "failed"

        self.db.flush()
        return job_node

    def _draft_timing(
        self,
        workflow: Workflow,
        config: WorkflowVersionConfig,
        tz_name: str,
        trigger: TriggerEvent,
    ) -> tuple[DraftState, datetime | None, datetime | None, datetime | None]:
        scheduled_from_trigger = _scheduled_publish_time(trigger, tz_name)
        recommended_at = None
        if config.timing.recommended_post_hour_utc is not None:
            now = datetime.now(timezone.utc)
            recommended_at = now.replace(
                hour=config.timing.recommended_post_hour_utc,
                minute=0,
                second=0,
                microsecond=0,
            )
            if recommended_at <= now:
                recommended_at += timedelta(days=1)
        if scheduled_from_trigger is not None:
            recommended_at = scheduled_from_trigger

        if workflow.mode == WorkflowMode.AUTOMATIC:
            scheduled_at = scheduled_from_trigger or recommended_at or (
                datetime.now(timezone.utc) + timedelta(minutes=config.timing.publish_delay_minutes)
            )
            return DraftState.AUTOMATIC_READY, recommended_at, scheduled_at, None

        return DraftState.MANUAL_READY, recommended_at, None, _end_of_day(tz_name)
