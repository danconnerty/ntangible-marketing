import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.lead import LeadAccount
from app.models.partner import PartnerAccount, PartnerEventRecord
from app.models.review import DraftVariant
from app.services.brain_query import BrainQuery
from app.services.trigger_engine import TriggerEngine
from app.services.workflow_engine import WorkflowEngine
from app.models.brain import EntityNode, KnowledgeNode
from app.models.workflow import Platform, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig


DEFAULT_PLAYBOOKS = [
    {
        "slug": "alliance-registration-push",
        "name": "Alliance Registration Push",
        "description": "Drive event registration with proof-led partner copy.",
        "playbook_type": "registration_push",
        "persona": "event_operator",
        "offer": "Register now",
        "cta": "Reserve your spot",
        "default_audience": "travel ball coaches",
        "default_proof_points": ["Pressure data", "event credibility"],
        "target_output": "linkedin",
        "metadata": {"partner_slug": "alliance_fastpitch"},
    },
    {
        "slug": "fss-roi-summary",
        "name": "FSS ROI Summary",
        "description": "Package proof and ROI messaging for Future Stars Series.",
        "playbook_type": "partner_roi_summary",
        "persona": "partner_operator",
        "offer": "See the partner ROI summary",
        "cta": "Share the data story",
        "default_audience": "event partners",
        "default_proof_points": ["Athlete volume", "partner proof"],
        "target_output": "linkedin",
        "metadata": {"partner_slug": "fss"},
    },
    {
        "slug": "coach-demo-push-linkedin",
        "name": "Coach Demo Push",
        "description": "Drive coach/demo interest with proof-led outreach.",
        "playbook_type": "demo_push",
        "persona": "coach",
        "offer": "Book a demo",
        "cta": "Book your walkthrough",
        "default_audience": "coaches and front offices",
        "default_proof_points": ["decision confidence", "pressure-performance context"],
        "target_output": "linkedin",
        "metadata": {},
    },
]


DEFAULT_GOALS = [
    {
        "slug": "alliance-registration-completions",
        "name": "Alliance Registration Completions",
        "metric_type": "registrations",
        "attribution_window_days": 14,
        "metadata": {"playbook_slug": "alliance-registration-push"},
    },
    {
        "slug": "demo-bookings-linkedin",
        "name": "Demo Bookings LinkedIn",
        "metric_type": "demo_requests",
        "attribution_window_days": 30,
        "metadata": {"playbook_slug": "coach-demo-push-linkedin"},
    },
    {
        "slug": "fss-roi-summary-followups",
        "name": "FSS ROI Summary Followups",
        "metric_type": "partner_followups",
        "attribution_window_days": 30,
        "metadata": {"playbook_slug": "fss-roi-summary"},
    },
]


class _PlaybookAdapter:
    """Wraps an EntityNode to expose the legacy RevenuePlaybook attribute interface
    expected by internal helper methods."""

    def __init__(self, entity: EntityNode) -> None:
        self._entity = entity

    @property
    def id(self) -> uuid.UUID:
        return self._entity.id

    @property
    def slug(self) -> str:
        return self._entity.slug

    @property
    def name(self) -> str:
        return self._entity.canonical_name

    @property
    def description(self) -> str:
        return self._entity.metadata_.get("description", "")

    @property
    def playbook_type(self) -> str:
        return self._entity.metadata_.get("playbook_type", "")

    @property
    def workflow_id(self) -> uuid.UUID | None:
        wid = self._entity.metadata_.get("workflow_id")
        if wid:
            return uuid.UUID(str(wid))
        return None

    @property
    def target_output(self) -> str | None:
        return self._entity.metadata_.get("target_output")

    @property
    def persona(self) -> str:
        return self._entity.metadata_.get("persona", "")

    @property
    def offer(self) -> str:
        return self._entity.metadata_.get("offer", "")

    @property
    def cta(self) -> str:
        return self._entity.metadata_.get("cta", "")

    @property
    def default_audience(self) -> str | None:
        return self._entity.metadata_.get("default_audience")

    @property
    def default_proof_points(self) -> list[str]:
        return self._entity.metadata_.get("default_proof_points") or []

    @property
    def active(self) -> bool:
        return self._entity.metadata_.get("active", True)


class RevenueService:
    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)
        self.trigger_engine = TriggerEngine(db)
        self.workflow_engine = WorkflowEngine(db)

    def list_dashboard(self) -> dict[str, list[dict[str, Any]]]:
        self._ensure_defaults()
        playbook_entities = sorted(
            self.bq.list_entities_by_type("playbook"),
            key=lambda e: e.canonical_name,
        )
        goal_nodes = sorted(
            self.bq.list_knowledge_by_kind("goal"),
            key=lambda n: n.title,
        )
        conversion_nodes = sorted(
            self.bq.list_knowledge_by_kind("conversion", limit=50),
            key=lambda n: n.created_at or "",
            reverse=True,
        )
        execution_nodes = sorted(
            self.bq.list_knowledge_by_kind("execution", limit=50),
            key=lambda n: n.created_at or "",
            reverse=True,
        )
        package_nodes = sorted(
            self.bq.list_knowledge_by_kind("sales_package", limit=50),
            key=lambda n: n.created_at or "",
            reverse=True,
        )
        return {
            "playbooks": [self._serialize_playbook(_PlaybookAdapter(e)) for e in playbook_entities],
            "executions": [self._serialize_execution(n) for n in execution_nodes],
            "conversion_goals": [self._serialize_goal(n) for n in goal_nodes],
            "conversion_events": [self._serialize_conversion(n) for n in conversion_nodes],
            "sales_packages": [self._serialize_sales_package(n) for n in package_nodes],
        }

    def run_playbook_by_slug(
        self,
        playbook_slug: str,
        *,
        actor: str,
        source_kind: str,
        source_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_defaults()
        playbook = self._get_playbook_by_slug(playbook_slug)
        if playbook is None:
            raise ValueError(f"Revenue playbook not found: {playbook_slug}")

        trigger = self._build_trigger(
            playbook,
            actor=actor,
            source_kind=source_kind,
            source_id=source_id,
            context=context or {},
        )
        job = self.workflow_engine.execute(trigger)
        execution_node = self.bq.create_knowledge_node(
            kind="execution",
            title=f"{playbook.name} execution",
            status=job.status,
            metadata={
                "playbook_entity_id": str(playbook.id),
                "playbook_slug": playbook.slug,
                "playbook_type": playbook.playbook_type,
                "source_kind": source_kind,
                "source_id": source_id,
                "trigger_event_id": str(trigger.id),
                "content_job_id": str(getattr(job, "id", "") or ""),
                "actor": actor,
                "intent": "revenue",
                "summary": {
                    "intent": "revenue",
                    "playbook_slug": playbook.slug,
                    "playbook_type": playbook.playbook_type,
                    "source_kind": source_kind,
                    "source_id": source_id,
                },
            },
        )
        self.bq.create_edge(
            source_id=playbook.id,
            target_id=execution_node.id,
            source_type="entity",
            target_type="knowledge",
            relation="has_execution",
        )
        packages = self._create_sales_packages(
            playbook,
            source_kind=source_kind,
            source_id=source_id,
            content_job_id=getattr(job, "id", None),
        )
        self.db.flush()
        return {
            "execution_id": str(execution_node.id),
            "playbook_slug": playbook.slug,
            "intent": "revenue",
            "status": job.status,
            "sales_package_count": len(packages),
        }

    def record_conversion_event(
        self,
        *,
        goal_slug: str,
        external_event_id: str,
        source_kind: str,
        source_reference: str,
        metric_value: float,
        metadata: dict[str, Any] | None = None,
        partner_slug: str | None = None,
        lead_account_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_defaults()
        goal = self._get_goal_by_slug(goal_slug)
        if goal is None:
            raise ValueError(f"Conversion goal not found: {goal_slug}")
        existing = self._find_conversion_event(goal.id, external_event_id)
        if existing is not None:
            return self._serialize_conversion(existing, goal_slug=goal_slug)

        event_node = self.bq.create_knowledge_node(
            kind="conversion",
            title=f"Conversion: {goal_slug} / {external_event_id}",
            status="active",
            metadata={
                "goal_node_id": str(goal.id),
                "goal_slug": goal_slug,
                "external_event_id": external_event_id,
                "source_kind": source_kind,
                "source_reference": source_reference,
                "partner_slug": partner_slug,
                "lead_account_id": lead_account_id,
                "metric_value": float(metric_value),
                **(metadata or {}),
            },
        )
        self.bq.create_edge(
            source_id=goal.id,
            target_id=event_node.id,
            source_type="knowledge",
            target_type="knowledge",
            relation="has_conversion",
        )
        self.db.flush()
        return self._serialize_conversion(event_node, goal_slug=goal_slug)

    def _ensure_defaults(self) -> None:
        for definition in DEFAULT_PLAYBOOKS:
            existing = self.bq.get_entity_by_slug("playbook", definition["slug"])
            if existing is not None:
                continue
            workflow = self._resolve_or_create_workflow(definition)
            self.bq.create_entity(
                entity_type="playbook",
                canonical_name=definition["name"],
                slug=definition["slug"],
                metadata={
                    "description": definition["description"],
                    "playbook_type": definition["playbook_type"],
                    "workflow_id": str(workflow.id),
                    "target_output": definition["target_output"],
                    "persona": definition["persona"],
                    "offer": definition["offer"],
                    "cta": definition["cta"],
                    "default_audience": definition["default_audience"],
                    "default_proof_points": definition["default_proof_points"],
                    "active": True,
                    **definition["metadata"],
                },
            )

        for definition in DEFAULT_GOALS:
            existing_goals = self.bq.list_knowledge_by_kind("goal")
            if any(g.metadata_.get("slug") == definition["slug"] for g in existing_goals):
                continue
            playbook_entity = self.bq.get_entity_by_slug("playbook", definition["metadata"]["playbook_slug"])
            goal_node = self.bq.create_knowledge_node(
                kind="goal",
                title=definition["name"],
                status="active",
                metadata={
                    "slug": definition["slug"],
                    "metric_type": definition["metric_type"],
                    "attribution_window_days": definition["attribution_window_days"],
                    "active": True,
                    **definition["metadata"],
                },
            )
            if playbook_entity is not None:
                self.bq.create_edge(
                    source_id=playbook_entity.id,
                    target_id=goal_node.id,
                    source_type="entity",
                    target_type="knowledge",
                    relation="has_goal",
                )

    def _resolve_or_create_workflow(self, definition: dict[str, Any]) -> Workflow:
        slug = f"revenue-{definition['slug']}"
        workflow = self.db.query(Workflow).filter(Workflow.slug == slug).first()
        if workflow is not None:
            return workflow

        target_output = definition["target_output"]
        platform = Platform(target_output) if target_output in {member.value for member in Platform} else Platform.LINKEDIN
        content_type = "company_update" if platform == Platform.LINKEDIN else "data_drop"
        if definition["playbook_type"] in {"landing_page_copy", "email_followup", "sales_one_pager"}:
            platform = Platform.NEWSLETTER
            content_type = "newsletter"

        workflow = Workflow(
            id=uuid.uuid4(),
            name=definition["name"],
            slug=slug,
            description=definition["description"],
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
                    "tone_notes": "Use proof-led, specific revenue language without sounding generic or pushy.",
                    "system_prompt_additions": "Treat this as conversion-oriented copy. Keep the CTA explicit and evidence-backed.",
                },
                retrieval={
                    "include_campaign_context": True,
                    "include_revenue_context": True,
                },
                routing={
                    "target_intent": "revenue",
                    "target_content_type": content_type,
                    "target_pillar": "client_proof",
                },
                cta={"cta_preferences": [definition["cta"]]},
            ).model_dump(),
            version_note="Bootstrapped revenue workflow",
            author="system",
            is_active=True,
        )
        self.db.add(version)
        self.db.flush()
        workflow.active_version_id = version.id
        self.db.flush()
        return workflow

    def _build_trigger(
        self,
        playbook: _PlaybookAdapter,
        *,
        actor: str,
        source_kind: str,
        source_id: str,
        context: dict[str, Any],
    ) -> Any:
        workflow_id = playbook.workflow_id
        if workflow_id is None:
            raise ValueError(f"Revenue playbook missing workflow: {playbook.slug}")

        source_context = self._build_source_context(source_kind, source_id)
        request_text = "\n".join(
            [
                f"Revenue playbook: {playbook.name}",
                f"Playbook type: {playbook.playbook_type}",
                f"Persona: {playbook.persona}",
                f"Offer: {playbook.offer}",
                f"CTA: {playbook.cta}",
                f"Audience: {playbook.default_audience or ''}",
                f"Proof points: {', '.join(playbook.default_proof_points or [])}",
            ]
        )
        trigger = self.trigger_engine.create_manual_request(request_text, workflow_id)
        trigger.source_payload = {
            **trigger.source_payload,
            **source_context,
            "actor": actor,
            "intent": "revenue",
            "revenue_context": {
                "playbook_slug": playbook.slug,
                "playbook_type": playbook.playbook_type,
                "persona": playbook.persona,
                "offer": playbook.offer,
                "cta": playbook.cta,
                "audience": playbook.default_audience,
                "proof_points": playbook.default_proof_points or [],
                **context,
            },
        }
        self.db.flush()
        return trigger

    def _build_source_context(self, source_kind: str, source_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"source_kind": source_kind, "source_id": source_id}
        if source_kind == "campaign":
            campaign = self.db.query(Campaign).filter(Campaign.id == uuid.UUID(source_id)).first()
            if campaign is not None:
                payload["campaign"] = {
                    "id": str(campaign.id),
                    "slug": campaign.slug,
                    "name": campaign.name,
                    "objective": campaign.objective,
                    "audience": campaign.audience,
                    "theme": campaign.theme,
                    "status": campaign.status.value,
                }
        elif source_kind == "lead":
            lead = self.db.query(LeadAccount).filter(LeadAccount.id == uuid.UUID(source_id)).first()
            if lead is not None:
                payload["lead"] = {
                    "id": str(lead.id),
                    "name": lead.name,
                    "stage": lead.stage,
                    "priority": lead.priority,
                    "metadata": lead.metadata_json or {},
                }
        elif source_kind == "partner_event":
            event = self.db.query(PartnerEventRecord).filter(PartnerEventRecord.id == uuid.UUID(source_id)).first()
            if event is not None:
                partner = self.db.query(PartnerAccount).filter(PartnerAccount.id == event.partner_account_id).first()
                payload["partner"] = {
                    "slug": partner.slug if partner is not None else None,
                    "name": partner.display_name if partner is not None else None,
                    "event_type": event.event_type,
                    "event_id": str(event.id),
                    "external_event_id": event.external_event_id,
                }
                payload["partner_slug"] = partner.slug if partner is not None else None
                payload["partner_name"] = partner.display_name if partner is not None else None
                payload["source_event_type"] = event.event_type
                payload["source_event_id"] = str(event.id)
        return payload

    def _create_sales_packages(
        self,
        playbook: _PlaybookAdapter,
        *,
        source_kind: str,
        source_id: str,
        content_job_id: uuid.UUID | None = None,
    ) -> list[Any]:
        if source_kind != "partner_event":
            return []
        try:
            event = self.db.query(PartnerEventRecord).filter(PartnerEventRecord.id == uuid.UUID(source_id)).first()
        except (ValueError, AttributeError):
            return []
        if event is None:
            return []
        partner = self.db.query(PartnerAccount).filter(PartnerAccount.id == event.partner_account_id).first()
        if partner is None:
            return []
        draft = None
        if content_job_id is not None:
            draft = (
                self.db.query(DraftVariant)
                .filter(DraftVariant.content_job_id == content_job_id)
                .order_by(DraftVariant.created_at.asc())
                .first()
            )
        package_node = self.bq.create_knowledge_node(
            kind="sales_package",
            title=playbook.offer,
            content=draft.content if draft is not None else playbook.description,
            status="needs_review",
            metadata={
                "partner_account_id": str(partner.id),
                "partner_event_record_id": str(event.id),
                "playbook_entity_id": str(playbook.id),
                "draft_variant_id": str(draft.id) if draft is not None else None,
                "package_kind": playbook.playbook_type,
                "headline": playbook.offer,
                "cta": playbook.cta,
                "payload": {
                    "partner_slug": partner.slug,
                    "partner_name": partner.display_name,
                    "playbook_slug": playbook.slug,
                    "event_type": event.event_type,
                },
                "usage_notes": "Partner-facing revenue enablement package.",
            },
        )
        self.bq.create_edge(
            source_id=playbook.id,
            target_id=package_node.id,
            source_type="entity",
            target_type="knowledge",
            relation="has_package",
        )
        return [package_node]

    def _get_playbook_by_slug(self, slug: str) -> _PlaybookAdapter | None:
        entity = self.bq.get_entity_by_slug("playbook", slug)
        if entity is None:
            return None
        return _PlaybookAdapter(entity)

    def _get_goal_by_slug(self, slug: str) -> KnowledgeNode | None:
        goals = self.bq.list_knowledge_by_kind("goal")
        for goal in goals:
            if goal.metadata_.get("slug") == slug:
                return goal
        return None

    def _find_conversion_event(self, goal_id: uuid.UUID, external_event_id: str) -> KnowledgeNode | None:
        conversions = self.bq.list_knowledge_by_kind("conversion")
        for node in conversions:
            if (
                node.metadata_.get("goal_node_id") == str(goal_id)
                and node.metadata_.get("external_event_id") == external_event_id
            ):
                return node
        return None

    def _serialize_playbook(self, playbook: _PlaybookAdapter) -> dict[str, Any]:
        return {
            "id": str(playbook.id),
            "slug": playbook.slug,
            "name": playbook.name,
            "playbook_type": playbook.playbook_type,
            "persona": playbook.persona,
            "offer": playbook.offer,
            "cta": playbook.cta,
            "active": playbook.active,
        }

    def _serialize_execution(self, node: KnowledgeNode) -> dict[str, Any]:
        meta = node.metadata_
        return {
            "id": str(node.id),
            "revenue_playbook_id": meta.get("playbook_entity_id", ""),
            "source_kind": meta.get("source_kind", ""),
            "source_id": meta.get("source_id", ""),
            "status": node.status,
            "summary": meta.get("summary", {}),
        }

    def _serialize_goal(self, node: KnowledgeNode) -> dict[str, Any]:
        meta = node.metadata_
        return {
            "id": str(node.id),
            "slug": meta.get("slug", ""),
            "name": node.title,
            "metric_type": meta.get("metric_type", ""),
            "active": meta.get("active", True),
            "attribution_window_days": meta.get("attribution_window_days", 30),
        }

    def _serialize_conversion(
        self, node: KnowledgeNode, goal_slug: str | None = None
    ) -> dict[str, Any]:
        meta = node.metadata_
        resolved_goal_slug = goal_slug or meta.get("goal_slug")
        return {
            "id": str(node.id),
            "goal_slug": resolved_goal_slug,
            "external_event_id": meta.get("external_event_id", ""),
            "source_kind": meta.get("source_kind", ""),
            "source_reference": meta.get("source_reference", ""),
            "metric_value": meta.get("metric_value", 0.0),
        }

    def _serialize_sales_package(self, node: KnowledgeNode) -> dict[str, Any]:
        meta = node.metadata_
        return {
            "id": str(node.id),
            "package_kind": meta.get("package_kind", ""),
            "status": node.status,
            "headline": meta.get("headline", ""),
            "cta": meta.get("cta", ""),
        }
