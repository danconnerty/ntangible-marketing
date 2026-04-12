import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.lead_nurture import LeadNurtureAgent
from app.models.brain import EntityNode, KnowledgeNode
from app.models.workflow import Platform, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.brain_query import BrainQuery
from app.services.memory_retrieval import MemoryRetrievalService
from app.services.trigger_engine import TriggerEngine
from app.services.workflow_engine import WorkflowEngine


class LeadNurtureService:
    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)
        self.agent = LeadNurtureAgent()
        self.memory = MemoryRetrievalService(db)
        self.trigger_engine = TriggerEngine(db)
        self.workflow_engine = WorkflowEngine(db)

    def list_dashboard(self) -> dict[str, list[dict[str, Any]]]:
        leads = self.bq.list_entities_by_type("lead", status="active")
        tasks = self.bq.list_knowledge_by_kind("nurture_task", limit=50)

        leads_by_id = {lead.id: lead for lead in leads}
        task_counts: dict[uuid.UUID, int] = {}
        for task in tasks:
            if task.status == "open":
                lead_id_str = task.metadata_.get("lead_entity_id")
                if lead_id_str:
                    try:
                        lead_id = uuid.UUID(lead_id_str)
                        task_counts[lead_id] = task_counts.get(lead_id, 0) + 1
                    except (ValueError, AttributeError):
                        pass

        return {
            "leads": [
                {
                    "id": str(lead.id),
                    "name": lead.canonical_name,
                    "stage": lead.metadata_.get("stage", "new"),
                    "priority": lead.metadata_.get("priority", "normal"),
                    "source": lead.metadata_.get("source", "manual"),
                    "open_task_count": task_counts.get(lead.id, 0),
                    "next_touchpoint": self.build_recommendations(lead)["touchpoint_type"],
                }
                for lead in leads
            ],
            "tasks": [
                {
                    "id": str(task.id),
                    "lead_id": task.metadata_.get("lead_entity_id", ""),
                    "lead_name": _lead_name_for_task(task, leads_by_id),
                    "task_type": task.metadata_.get("task_type", ""),
                    "status": task.status,
                    "summary": task.title,
                }
                for task in tasks
            ],
        }

    def build_recommendations(self, lead: EntityNode) -> dict[str, Any]:
        metadata = lead.metadata_ or {}
        query = " ".join(
            filter(
                None,
                [
                    lead.canonical_name,
                    metadata.get("stage", ""),
                    metadata.get("priority", ""),
                    str(metadata.get("sport", "")),
                    str(metadata.get("segment", "")),
                ],
            )
        )
        examples = self.memory.build_generation_context(
            query=query,
            platform=Platform.LINKEDIN,
            approved_limit=3,
            rejected_limit=2,
        )
        # The agent uses getattr(lead, "stage") and getattr(lead, "name"), so
        # we pass a thin adapter that surfaces metadata fields as attributes.
        lead_adapter = _LeadAdapter(lead)
        return self.agent.recommend_touchpoint(lead_adapter, examples)

    def generate_content(
        self,
        lead_id: uuid.UUID,
        *,
        platform: str,
        actor: str = "sales",
    ) -> dict[str, Any]:
        lead = self._get_lead(lead_id)
        workflow = self._resolve_lead_workflow(platform)
        recommendation = self.build_recommendations(lead)
        meta = lead.metadata_ or {}
        request_text = "\n".join(
            [
                f"Lead nurture content for {lead.canonical_name}",
                f"Stage: {meta.get('stage', 'new')}",
                f"Priority: {meta.get('priority', 'normal')}",
                f"Touchpoint: {recommendation['touchpoint_type']}",
                f"Summary: {recommendation['summary']}",
                "Generate content that moves the lead one step forward without sounding generic.",
            ]
        )
        trigger = self.trigger_engine.create_manual_request(request_text, workflow.id)
        trigger.source_payload = {
            **trigger.source_payload,
            "lead_account_id": str(lead.id),
            "lead_name": lead.canonical_name,
            "lead_stage": meta.get("stage", "new"),
            "lead_priority": meta.get("priority", "normal"),
            "lead": {
                "id": str(lead.id),
                "name": lead.canonical_name,
                "stage": meta.get("stage", "new"),
                "priority": meta.get("priority", "normal"),
                "metadata": meta,
            },
            "lead_nurture": recommendation,
            "actor": actor,
        }
        job = self.workflow_engine.execute(trigger)

        task = self.bq.create_knowledge_node(
            kind="nurture_task",
            title=recommendation["summary"],
            status="queued" if job.status != "failed" else "failed",
            metadata={
                "lead_entity_id": str(lead.id),
                "workflow_id": str(workflow.id),
                "trigger_event_id": str(trigger.id),
                "task_type": recommendation["touchpoint_type"],
                "actor": actor,
                "job_status": job.status,
            },
        )

        return {
            "lead_id": str(lead.id),
            "workflow_slug": workflow.slug,
            "trigger_event_id": str(trigger.id),
            "status": job.status,
            "task_id": str(task.id),
            "platform": platform,
        }

    def _get_lead(self, lead_id: uuid.UUID) -> EntityNode:
        lead = self.bq.get_entity(lead_id)
        if lead is None or lead.entity_type != "lead":
            raise ValueError(f"Lead not found: {lead_id}")
        return lead

    def _resolve_lead_workflow(self, platform: str) -> Workflow:
        platform_enum = Platform(platform)
        slug = f"lead-nurture-{platform_enum.value}"
        workflow = self.db.query(Workflow).filter(Workflow.slug == slug).first()
        if workflow:
            return workflow

        workflow = Workflow(
            id=uuid.uuid4(),
            name=f"Lead Nurture {platform_enum.value.title()}",
            slug=slug,
            description="Manual-first lead nurture drafts routed through the control room.",
            mode=WorkflowMode.MANUAL,
            platform=platform_enum,
            content_type="lead_nurture",
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
                    "tone_notes": "Make the message specific to the lead stage and keep it proof-led.",
                    "system_prompt_additions": "Avoid generic sales language. Use evidence and forward motion.",
                },
                routing={
                    "target_content_type": "lead_nurture",
                    "target_intent": "revenue",
                    "target_pillar": "client_proof",
                },
            ).model_dump(),
            version_note="Bootstrapped lead nurture workflow",
            author="system",
            is_active=True,
        )
        self.db.add(version)
        self.db.flush()
        workflow.active_version_id = version.id
        self.db.flush()
        return workflow


class _LeadAdapter:
    """Adapts an EntityNode(entity_type='lead') to the attribute interface expected
    by LeadNurtureAgent (which uses getattr(lead, 'stage') and getattr(lead, 'name')).
    """

    def __init__(self, entity: EntityNode) -> None:
        self._entity = entity
        meta = entity.metadata_ or {}
        self.id = entity.id
        self.name = entity.canonical_name
        self.stage = meta.get("stage", "new")
        self.priority = meta.get("priority", "normal")
        self.source = meta.get("source", "manual")
        self.metadata_json = meta


def _lead_name_for_task(task: KnowledgeNode, leads_by_id: dict[uuid.UUID, EntityNode]) -> str:
    lead_id_str = task.metadata_.get("lead_entity_id")
    if not lead_id_str:
        return "Unknown lead"
    try:
        lead_id = uuid.UUID(lead_id_str)
        lead = leads_by_id.get(lead_id)
        return lead.canonical_name if lead else "Unknown lead"
    except (ValueError, AttributeError):
        return "Unknown lead"
