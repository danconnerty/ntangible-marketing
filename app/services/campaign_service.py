import uuid
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.agents.campaign_planner import CampaignPlannerAgent
from app.models.brain import EntityNode, KnowledgeNode
from app.models.workflow import Workflow
from app.services.brain_query import BrainQuery
from app.services.workflow_engine import WorkflowEngine


class CampaignService:
    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)
        self.agent = CampaignPlannerAgent()
        self.workflow_engine = WorkflowEngine(db)

    def list_campaigns(self) -> list[dict[str, Any]]:
        entities = self.bq.list_entities_by_type("campaign", status="active", limit=50)
        # Also include non-active statuses by querying all statuses
        all_statuses = ["active", "paused", "completed", "draft"]
        seen_ids: set[uuid.UUID] = {e.id for e in entities}
        for status in ["paused", "completed", "draft"]:
            for e in self.bq.list_entities_by_type("campaign", status=status, limit=50):
                if e.id not in seen_ids:
                    entities.append(e)
                    seen_ids.add(e.id)

        return [
            {
                "id": str(entity.id),
                "name": entity.metadata_.get("name") or entity.canonical_name,
                "slug": entity.slug,
                "status": entity.status,
                "objective": entity.metadata_.get("objective"),
                "audience": entity.metadata_.get("audience"),
                "theme": entity.metadata_.get("theme"),
                "start_date": entity.metadata_.get("start_date"),
                "end_date": entity.metadata_.get("end_date"),
                "workflow_count": self._workflow_count(entity.id),
            }
            for entity in entities
        ]

    def run_campaign_by_slug(self, campaign_slug: str, actor: str = "planner") -> dict[str, Any]:
        campaign = self._get_campaign_by_slug(campaign_slug)
        if campaign is None:
            raise ValueError(f"Campaign not found: {campaign_slug}")
        return self.run_campaign(campaign.id, actor=actor)

    def run_campaign(self, campaign_id: uuid.UUID, actor: str = "planner") -> dict[str, Any]:
        campaign = self._get_campaign_by_id(campaign_id)
        if campaign is None:
            raise ValueError(f"Campaign not found: {campaign_id}")

        scopes = self._get_scopes_for_campaign(campaign.id)
        if not scopes:
            slug = campaign.slug
            raise ValueError(f"No workflows mapped to campaign {slug}")

        campaign_slug = campaign.slug
        campaign_name = campaign.metadata_.get("name") or campaign.canonical_name
        workflow_runs: list[dict[str, Any]] = []

        for scope_edge in scopes:
            workflow_entity = self._get_workflow_entity(scope_edge.target_id)
            if workflow_entity is None or workflow_entity.metadata_.get("enabled") is False:
                raise ValueError(f"No enabled workflow found for scope {scope_edge.target_id}")

            # Resolve legacy Workflow for CampaignPlannerAgent compatibility
            workflow = self.db.query(Workflow).filter(Workflow.slug == workflow_entity.slug).first()
            role = scope_edge.metadata_.get("role", "")

            # Build request text via planner agent using campaign context namespace
            request_text = self.agent.build_manual_request(
                _CampaignContext(campaign),
                _WorkflowContext(workflow_entity, workflow),
            )

            # Create a brain trigger node for execute_brain
            trigger_node = self.bq.create_knowledge_node(
                kind="trigger",
                title=f"Campaign trigger: {campaign_slug} / {workflow_entity.slug}",
                status="active",
                confidence=1.0,
                trust_score=1.0,
                metadata={
                    "trigger_type": "manual",
                    "request": request_text,
                    "workflow_entity_id": str(workflow_entity.id),
                    "campaign": self._campaign_trigger_fields(campaign, role),
                    **self._campaign_trigger_fields(campaign, role),
                },
            )

            job_node = self.workflow_engine.execute_brain(trigger_node)

            summary_message = job_node.metadata_.get("error") or self._default_summary(
                workflow_entity.slug, job_node.status
            )
            run_summary = {
                "message": summary_message,
                "job_status": job_node.status,
                "content_job_id": str(job_node.id),
            }

            # Record campaign run as a KnowledgeNode
            run_node = self.bq.create_knowledge_node(
                kind="campaign_run",
                title=f"Campaign run: {campaign_slug} / {workflow_entity.slug}",
                status=job_node.status,
                metadata={
                    "campaign_id": str(campaign.id),
                    "workflow_entity_id": str(workflow_entity.id),
                    "trigger_node_id": str(trigger_node.id),
                    "job_node_id": str(job_node.id),
                    "actor": actor,
                    "summary": run_summary,
                },
            )
            self.bq.create_edge(
                source_id=campaign.id,
                target_id=run_node.id,
                source_type="entity",
                target_type="knowledge",
                relation="has_run",
            )

            workflow_name = workflow_entity.metadata_.get("name") or workflow_entity.canonical_name
            workflow_runs.append(
                {
                    "workflow_id": str(workflow_entity.id),
                    "workflow_slug": workflow_entity.slug,
                    "workflow_name": workflow_name,
                    "role": role,
                    "trigger_event_id": str(trigger_node.id),
                    "content_job_id": str(job_node.id),
                    "status": job_node.status,
                    "summary": summary_message,
                    "summary_details": run_summary,
                }
            )

        return {
            "campaign_id": str(campaign.id),
            "campaign_slug": campaign_slug,
            "campaign_name": campaign_name,
            "actor": actor,
            "workflow_runs": workflow_runs,
        }

    def get_campaign_detail(self, campaign_id: uuid.UUID) -> dict[str, Any] | None:
        campaign = self._get_campaign_by_id(campaign_id)
        if campaign is None:
            return None

        scopes = self._get_scopes_for_campaign(campaign.id)
        workflow_ids = [str(e.target_id) for e in scopes]

        runs = self.bq.list_knowledge_by_kind("campaign_run", limit=50)
        campaign_runs = [
            r for r in runs
            if r.metadata_.get("campaign_id") == str(campaign.id)
        ]

        return {
            "id": str(campaign.id),
            "name": campaign.metadata_.get("name") or campaign.canonical_name,
            "slug": campaign.slug,
            "status": campaign.status,
            "objective": campaign.metadata_.get("objective"),
            "audience": campaign.metadata_.get("audience"),
            "theme": campaign.metadata_.get("theme"),
            "start_date": campaign.metadata_.get("start_date"),
            "end_date": campaign.metadata_.get("end_date"),
            "workflow_ids": workflow_ids,
            "run_count": len(campaign_runs),
            "recent_runs": [
                {
                    "id": str(r.id),
                    "status": r.status,
                    "actor": r.metadata_.get("actor"),
                    "summary": r.metadata_.get("summary", {}),
                }
                for r in campaign_runs[:5]
            ],
        }

    def _default_summary(self, workflow_slug: str, status: str) -> str:
        if status == "completed":
            return f"Workflow {workflow_slug} completed via campaign manual request."
        return f"Workflow {workflow_slug} ended with status {status}."

    def _workflow_count(self, campaign_id: uuid.UUID) -> int:
        return len(self._get_scopes_for_campaign(campaign_id))

    def _campaign_trigger_fields(self, campaign: EntityNode, role: str) -> dict[str, Any]:
        meta = campaign.metadata_
        return {
            "id": str(campaign.id),
            "slug": campaign.slug,
            "name": meta.get("name") or campaign.canonical_name,
            "objective": meta.get("objective"),
            "audience": meta.get("audience"),
            "theme": meta.get("theme"),
            "status": campaign.status,
            "role": role,
            "start_date": meta.get("start_date"),
            "end_date": meta.get("end_date"),
            "campaign_id": str(campaign.id),
            "campaign_slug": campaign.slug,
            "campaign_name": meta.get("name") or campaign.canonical_name,
            "campaign_objective": meta.get("objective"),
            "campaign_audience": meta.get("audience"),
            "campaign_theme": meta.get("theme"),
            "campaign_status": campaign.status,
            "campaign_role": role,
            "campaign_start_date": meta.get("start_date"),
            "campaign_end_date": meta.get("end_date"),
        }

    def _get_campaign_by_id(self, campaign_id: uuid.UUID) -> EntityNode | None:
        return self.bq.get_entity(campaign_id)

    def _get_campaign_by_slug(self, campaign_slug: str) -> EntityNode | None:
        return self.bq.get_entity_by_slug("campaign", campaign_slug)

    def _get_scopes_for_campaign(self, campaign_id: uuid.UUID):
        """Return EntityEdges with relation='scopes' from campaign to workflow entities."""
        from app.models.brain import EntityEdge
        return (
            self.db.query(EntityEdge)
            .filter(
                EntityEdge.source_id == campaign_id,
                EntityEdge.relation == "scopes",
            )
            .all()
        )

    def _get_workflow_entity(self, workflow_entity_id: uuid.UUID) -> EntityNode | None:
        return self.bq.get_entity(workflow_entity_id)


class _CampaignContext:
    """Adapter that makes an EntityNode look like a Campaign for CampaignPlannerAgent."""

    def __init__(self, entity: EntityNode):
        self._entity = entity
        meta = entity.metadata_
        self.name = meta.get("name") or entity.canonical_name
        self.slug = entity.slug
        self.objective = meta.get("objective")
        self.audience = meta.get("audience")
        self.theme = meta.get("theme")
        self.status = type("_Status", (), {"value": entity.status})()


class _WorkflowContext:
    """Adapter that makes an EntityNode look like a Workflow for CampaignPlannerAgent."""

    def __init__(self, entity: EntityNode, legacy_workflow: Workflow | None = None):
        self._entity = entity
        if legacy_workflow is not None:
            self.name = legacy_workflow.name
            self.slug = legacy_workflow.slug
            self.platform = legacy_workflow.platform
            self.content_type = legacy_workflow.content_type
        else:
            meta = entity.metadata_
            self.name = meta.get("name") or entity.canonical_name
            self.slug = entity.slug
            self.platform = type("_Platform", (), {"value": meta.get("platform", "")})()
            self.content_type = meta.get("content_type", "")
