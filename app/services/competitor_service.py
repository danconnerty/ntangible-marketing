import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.competitor_scout import CompetitorScoutAgent
from app.models.workflow import Platform, Workflow, WorkflowMode, WorkflowVersion
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.brain_query import BrainQuery
from app.services.trigger_engine import TriggerEngine
from app.services.workflow_engine import WorkflowEngine


class CompetitorService:
    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)
        self.agent = CompetitorScoutAgent()
        self.trigger_engine = TriggerEngine(db)
        self.workflow_engine = WorkflowEngine(db)

    def list_dashboard(self) -> dict[str, list[dict[str, Any]]]:
        sources = sorted(
            self.bq.list_entities_by_type("competitor"),
            key=lambda e: e.canonical_name,
        )
        signals = self.bq.list_knowledge_by_kind("signal", limit=50)
        signals = sorted(signals, key=lambda n: n.created_at or "", reverse=True)

        # Build a lookup from competitor entity id → entity for signal source names
        entity_by_id: dict[uuid.UUID, Any] = {e.id: e for e in sources}

        def _signal_source_name(signal_node: Any) -> str:
            # Signals have an edge: competitor entity → signal knowledge node
            # Edge is stored as EntityEdge(source=competitor, target=signal, relation="has_signal")
            # We resolve via metadata_ first (fast path), then fall back to edge lookup
            competitor_id = signal_node.metadata_.get("competitor_entity_id")
            if competitor_id:
                try:
                    entity = entity_by_id.get(uuid.UUID(str(competitor_id)))
                    if entity:
                        return entity.canonical_name
                except (ValueError, AttributeError):
                    pass
            return "Unknown source"

        return {
            "sources": [
                {
                    "id": str(source.id),
                    "slug": source.slug,
                    "display_name": source.canonical_name,
                    "source_url": source.metadata_.get("source_url"),
                    "platform": source.metadata_.get("platform"),
                    "active": source.metadata_.get("active", True),
                }
                for source in sources
            ],
            "signals": [
                {
                    "id": str(signal.id),
                    "source_name": _signal_source_name(signal),
                    "signal_type": signal.metadata_.get("signal_type"),
                    "summary": signal.content or signal.title,
                    "severity": signal.metadata_.get("severity"),
                    "reaction_angle": signal.metadata_.get("reaction_angle"),
                    "status": signal.status,
                }
                for signal in signals
            ],
        }

    def ingest_observation(self, payload: dict[str, Any]) -> dict[str, Any]:
        source = self._ensure_source(payload["source_slug"], payload)
        observation = self._create_observation(source, payload)
        classification = self.agent.classify_observation(payload)
        signal = self._create_signal(source, observation, classification)
        auto_runs = self._auto_response_runs(signal, payload)
        self.db.flush()
        result = self._serialize_signal(signal, source)
        result["auto_runs"] = auto_runs
        result["auto_responded"] = bool(auto_runs)
        return result

    def create_response_trigger(
        self,
        signal_id: uuid.UUID,
        *,
        platform: str,
        actor: str = "analyst",
    ) -> dict[str, Any]:
        signal = self._get_signal(signal_id)
        workflow = self._resolve_response_workflow(platform)
        payload = {
            "event_type": "competitor_signal",
            "competitor_signal_id": str(signal.id),
            "competitor_summary": signal.content or signal.title,
            "competitor_signal_type": signal.metadata_.get("signal_type"),
            "competitor_severity": signal.metadata_.get("severity"),
            "competitor_reaction_angle": signal.metadata_.get("reaction_angle"),
            "request": self._build_request_text(signal),
            "competitor": {
                "id": str(signal.id),
                "summary": signal.content or signal.title,
                "signal_type": signal.metadata_.get("signal_type"),
                "severity": signal.metadata_.get("severity"),
                "reaction_angle": signal.metadata_.get("reaction_angle"),
                "actor": actor,
            },
        }
        trigger = self.trigger_engine.ingest_external(payload, workflow.id)
        job = self.workflow_engine.execute(trigger)
        # Update signal status via metadata_ mutation
        signal.status = "queued" if job.status != "failed" else "failed"
        self.db.flush()
        return {
            "signal_id": str(signal.id),
            "workflow_slug": workflow.slug,
            "trigger_event_id": str(trigger.id),
            "status": job.status,
            "platform": platform,
        }

    def _build_request_text(self, signal: Any) -> str:
        parts = [
            "Create a proof-led response draft to a competitor market signal.",
            f"Signal: {signal.content or signal.title}",
            f"Type: {signal.metadata_.get('signal_type')}",
            f"Severity: {signal.metadata_.get('severity')}",
        ]
        reaction_angle = signal.metadata_.get("reaction_angle")
        if reaction_angle:
            parts.append(f"Angle: {reaction_angle}")
        parts.append("Do not imitate the competitor directly. Frame the response through NTangible's evidence and operating system.")
        return "\n".join(parts)

    def _auto_response_runs(
        self,
        signal: Any,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        explicit_platforms = payload.get("auto_platforms")
        if explicit_platforms:
            platforms = [str(platform) for platform in explicit_platforms]
        else:
            severity = signal.metadata_.get("severity", "low")
            if severity == "high":
                platforms = ["linkedin", "x"]
            elif severity == "medium":
                platforms = ["linkedin"]
            else:
                platforms = []

        runs: list[dict[str, Any]] = []
        actor = payload.get("actor", "competitor_scout")
        for platform in platforms:
            try:
                runs.append(
                    self.create_response_trigger(
                        signal.id,
                        platform=platform,
                        actor=actor,
                    )
                )
            except ValueError:
                continue
        return runs

    def _ensure_source(self, slug: str, payload: dict[str, Any]) -> Any:
        existing = self.bq.get_entity_by_slug("competitor", slug)
        if existing:
            return existing
        display_name = payload.get("display_name") or slug.replace("-", " ").replace("_", " ").title()
        return self.bq.create_entity(
            entity_type="competitor",
            canonical_name=display_name,
            slug=slug,
            metadata={
                "source_url": payload.get("source_url") or payload.get("url"),
                "platform": payload.get("platform") or "web",
                "active": True,
            },
        )

    def _create_observation(self, source: Any, payload: dict[str, Any]) -> Any:
        url = payload.get("url")
        if url:
            # Check for existing observation with same URL under this competitor
            existing_nodes = self.bq.list_knowledge_by_kind("observation")
            for node in existing_nodes:
                if (
                    node.metadata_.get("source_entity_id") == str(source.id)
                    and node.metadata_.get("url") == url
                ):
                    # Update raw payload
                    node.metadata_ = {**node.metadata_, "raw_payload": payload}
                    self.db.flush()
                    return node

        headline = payload.get("headline") or payload.get("summary") or "Competitor update"
        node = self.bq.create_knowledge_node(
            kind="observation",
            title=headline,
            content=payload.get("summary"),
            status="active",
            metadata={
                "source_entity_id": str(source.id),
                "url": url,
                "raw_payload": payload,
            },
        )
        self.bq.create_edge(
            source_id=source.id,
            target_id=node.id,
            source_type="entity",
            target_type="knowledge",
            relation="has_observation",
        )
        return node

    def _create_signal(
        self,
        source: Any,
        observation: Any,
        classification: dict[str, Any],
    ) -> Any:
        summary = classification["summary"]
        node = self.bq.create_knowledge_node(
            kind="signal",
            title=summary,
            content=summary,
            status="open",
            metadata={
                "competitor_entity_id": str(source.id),
                "observation_node_id": str(observation.id),
                "signal_type": classification["signal_type"],
                "severity": classification.get("severity", "low"),
                "reaction_angle": classification.get("reaction_angle"),
                "raw_payload": {
                    "classification": classification,
                    "observation": observation.metadata_.get("raw_payload"),
                },
            },
        )
        self.bq.create_edge(
            source_id=source.id,
            target_id=node.id,
            source_type="entity",
            target_type="knowledge",
            relation="has_signal",
        )
        return node

    def _get_signal(self, signal_id: uuid.UUID) -> Any:
        node = self.bq.get_knowledge_node(signal_id)
        if node is None or node.kind != "signal":
            raise ValueError(f"Competitor signal not found: {signal_id}")
        return node

    def _resolve_response_workflow(self, platform: str) -> Workflow:
        platform_enum = Platform(platform)
        slug = f"competitor-response-{platform_enum.value}"
        workflow = self.db.query(Workflow).filter(Workflow.slug == slug).first()
        if workflow:
            return workflow

        workflow = Workflow(
            id=uuid.uuid4(),
            name=f"Competitor Response {platform_enum.value.title()}",
            slug=slug,
            description="Manual-first competitor response drafts routed through the control room.",
            mode=WorkflowMode.MANUAL,
            platform=platform_enum,
            content_type="competitor_response",
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
                    "tone_notes": "Stay proof-led, specific, and non-reactive.",
                    "system_prompt_additions": "Never name or quote a competitor unless the operator explicitly asks for it.",
                },
                routing={
                    "target_content_type": "competitor_response",
                    "target_intent": "brand",
                    "target_pillar": "thought_leadership",
                },
            ).model_dump(),
            version_note="Bootstrapped competitor response workflow",
            author="system",
            is_active=True,
        )
        self.db.add(version)
        self.db.flush()
        workflow.active_version_id = version.id
        self.db.flush()
        return workflow

    def _serialize_signal(self, signal: Any, source: Any) -> dict[str, Any]:
        return {
            "signal_id": str(signal.id),
            "source_id": str(source.id),
            "source_slug": source.slug,
            "source_name": source.canonical_name,
            "signal_type": signal.metadata_.get("signal_type"),
            "summary": signal.content or signal.title,
            "severity": signal.metadata_.get("severity"),
            "reaction_angle": signal.metadata_.get("reaction_angle"),
            "status": signal.status,
        }
