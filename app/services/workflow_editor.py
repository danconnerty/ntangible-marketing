import copy
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.brain import EntityNode, KnowledgeNode
from app.models.memory import MemoryBucket
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.brain_query import BrainQuery
from app.services.memory_retrieval import MemoryRetrievalService


@dataclass
class _WorkflowProxy:
    """Thin read-only proxy that gives templates the same attribute surface as the old Workflow ORM row."""

    id: uuid.UUID
    name: str
    slug: str
    platform: Any  # string value; templates call .value on it
    mode: str
    timezone: str
    description: str | None = None

    class _PlatformValue:
        """Makes ``workflow.platform.value`` work when platform is already a string."""

        def __init__(self, value: str) -> None:
            self.value = value

        def __str__(self) -> str:
            return self.value

    @classmethod
    def from_entity(cls, entity: EntityNode) -> "_WorkflowProxy":
        meta = entity.metadata_ or {}
        platform_str = meta.get("platform", "")
        return cls(
            id=entity.id,
            name=entity.canonical_name,
            slug=entity.slug,
            platform=cls._PlatformValue(platform_str),
            mode=meta.get("mode", "manual"),
            timezone=meta.get("timezone", "UTC"),
            description=entity.description,
        )


@dataclass
class _VersionProxy:
    """Thin proxy with the same attribute surface as the old WorkflowVersion ORM row."""

    id: uuid.UUID
    version_number: int
    config: dict
    version_note: str | None
    author: str
    is_active: bool

    @classmethod
    def from_node(cls, node: KnowledgeNode) -> "_VersionProxy":
        meta = node.metadata_ or {}
        return cls(
            id=node.id,
            version_number=node.version,
            config=meta.get("config", {}),
            version_note=meta.get("version_note"),
            author=meta.get("author", "system"),
            is_active=node.status == "active",
        )


class WorkflowEditor:
    def __init__(self, db: Session):
        self.db = db
        self.memory = MemoryRetrievalService(db)

    def build_proposed_config(
        self,
        current_config: dict[str, Any],
        *,
        feedback: str,
        approved_example_ids: list[str],
        rejected_example_ids: list[str],
    ) -> dict[str, Any]:
        proposed = copy.deepcopy(current_config)
        config = WorkflowVersionConfig(**proposed)
        feedback_text = feedback.lower()

        tone_notes = [config.prompt.tone_notes] if config.prompt.tone_notes else []
        system_additions = [config.prompt.system_prompt_additions] if config.prompt.system_prompt_additions else []

        if "corporate" in feedback_text:
            tone_notes.append("Write in a direct founder-led voice, not corporate or press-release language.")
        if "athlete" in feedback_text or "coach" in feedback_text or "parent" in feedback_text:
            tone_notes.append("Write in athlete-facing language that also feels clear to coaches and parents.")
        if "data" in feedback_text or "proof" in feedback_text or "evidence" in feedback_text:
            system_additions.append("Lead with concrete data, proof, or a specific observation when supported by approved examples.")
        if "short" in feedback_text or "shorter" in feedback_text:
            system_additions.append("Keep paragraphs short and front-load the strongest idea.")
        if "cta" in feedback_text:
            config.cta.cta_rules = "Use one clear CTA only and avoid stacking asks."
        if "hook" in feedback_text:
            system_additions.append("Open with a sharper hook that states the tension or insight immediately.")

        config.prompt.tone_notes = " ".join(note for note in tone_notes if note).strip()
        config.prompt.system_prompt_additions = " ".join(note for note in system_additions if note).strip()
        config.retrieval.approved_example_ids = approved_example_ids
        config.retrieval.rejected_example_ids = rejected_example_ids
        config.retrieval.max_examples = max(config.retrieval.max_examples, min(len(approved_example_ids), 5))
        return config.model_dump()

    def propose_version(
        self,
        workflow_slug: str,
        *,
        feedback: str,
        actor: str = "claude",
        draft_id: str | None = None,
    ) -> dict[str, Any]:
        entity = self._get_workflow(workflow_slug)
        current = self._get_active_version(entity)

        self.memory.sync_control_room_memory()
        context_query = feedback or entity.canonical_name
        platform_str = entity.metadata_.get("platform", "")
        # MemoryRetrievalService.build_generation_context expects a Platform enum;
        # import lazily to avoid coupling if Platform is unavailable
        from app.models.workflow import Platform
        try:
            platform_enum = Platform(platform_str)
        except ValueError:
            platform_enum = Platform.LINKEDIN

        examples = self.memory.build_generation_context(
            query=context_query,
            platform=platform_enum,
            workflow_slug=entity.slug,
        )
        proposed_config = self.build_proposed_config(
            current.config,
            feedback=feedback,
            approved_example_ids=[item["id"] for item in examples["approved_examples"]],
            rejected_example_ids=[item["id"] for item in examples["rejected_examples"]],
        )

        # Find highest version number for this workflow
        existing_versions = self._list_versions(entity.id)
        version_number = 1 if not existing_versions else max(v.version_number for v in existing_versions) + 1

        bq = BrainQuery(self.db)
        node = bq.create_knowledge_node(
            kind="workflow_config",
            title=f"{entity.canonical_name} v{version_number}",
            status="pending",
            metadata={
                "config": proposed_config,
                "version_note": feedback,
                "author": actor,
                "workflow_id": str(entity.id),
            },
        )
        # Set the version number field
        node.version = version_number
        self.db.flush()

        # Link workflow entity → version config node
        bq.create_edge(
            source_id=entity.id,
            target_id=node.id,
            source_type="entity",
            target_type="knowledge",
            relation="has_config",
        )

        changes = self._diff_configs(current.config, proposed_config)
        return {
            "workflow": {
                "name": entity.canonical_name,
                "slug": entity.slug,
                "platform": entity.metadata_.get("platform", ""),
            },
            "draft_id": draft_id,
            "current_version": current.version_number,
            "proposed_version": version_number,
            "changes": changes,
            "approved_examples": examples["approved_examples"],
            "rejected_examples": examples["rejected_examples"],
            "version_id": str(node.id),
        }

    def activate_version(self, workflow_slug: str, version_number: int) -> _VersionProxy:
        entity = self._get_workflow(workflow_slug)
        versions = self._list_versions(entity.id)
        if not versions:
            raise ValueError("Workflow has no versions")

        selected = None
        for proxy in versions:
            is_selected = proxy.version_number == version_number
            # Update the underlying node status
            node = self.db.query(KnowledgeNode).filter(KnowledgeNode.id == proxy.id).first()
            if node is not None:
                node.status = "active" if is_selected else "superseded"
                meta = dict(node.metadata_)
                meta["is_active"] = is_selected
                node.metadata_ = meta
            if is_selected:
                selected = proxy
                selected.is_active = True

        if selected is None:
            raise ValueError(f"Version {version_number} not found for workflow {workflow_slug}")

        # Store active version ID in workflow metadata
        meta = dict(entity.metadata_)
        meta["active_version_id"] = str(selected.id)
        entity.metadata_ = meta
        self.db.flush()
        return selected

    def get_workflow_detail(self, workflow_slug: str) -> dict[str, Any]:
        entity = self._get_workflow(workflow_slug)
        versions = self._list_versions(entity.id)
        workflow_proxy = _WorkflowProxy.from_entity(entity)

        self.memory.sync_control_room_memory()
        platform_str = entity.metadata_.get("platform", "")
        from app.models.workflow import Platform
        try:
            platform_enum = Platform(platform_str)
        except ValueError:
            platform_enum = Platform.LINKEDIN

        approved_examples = self.memory.search(
            query=entity.canonical_name,
            platform=platform_enum,
            bucket=MemoryBucket.APPROVED,
            workflow_slug=entity.slug,
            limit=5,
        )
        rejected_examples = self.memory.search(
            query=entity.canonical_name,
            platform=platform_enum,
            bucket=MemoryBucket.REJECTED,
            workflow_slug=entity.slug,
            limit=5,
        )

        active_version_id_str = entity.metadata_.get("active_version_id")
        active_version = None
        if active_version_id_str:
            try:
                active_version_id = uuid.UUID(active_version_id_str)
                active_version = next((v for v in versions if v.id == active_version_id), None)
            except ValueError:
                pass
        if active_version is None and versions:
            # Fall back to the highest version number
            active_version = max(versions, key=lambda v: v.version_number)

        return {
            "workflow": workflow_proxy,
            "active_version": active_version,
            "versions": versions,
            "approved_examples": approved_examples,
            "rejected_examples": rejected_examples,
        }

    def _get_workflow(self, workflow_slug: str) -> EntityNode:
        entity = BrainQuery(self.db).get_entity_by_slug("workflow", workflow_slug)
        if entity is None:
            raise ValueError(f"Workflow {workflow_slug} not found")
        return entity

    def _get_active_version(self, entity: EntityNode) -> _VersionProxy:
        versions = self._list_versions(entity.id)
        if not versions:
            raise ValueError(f"Workflow {entity.slug} has no versions")
        # Prefer the node with status="active"
        active = next((v for v in versions if v.is_active), None)
        if active is None:
            # Fall back to highest version number
            active = max(versions, key=lambda v: v.version_number)
        return active

    def _list_versions(self, workflow_id: uuid.UUID) -> list[_VersionProxy]:
        """Return all workflow_config KnowledgeNodes linked from this workflow entity."""
        bq = BrainQuery(self.db)
        edges = bq.get_edges_from(workflow_id, relation="has_config")
        config_ids = {edge.target_id for edge in edges}
        if not config_ids:
            return []

        nodes = (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.id.in_(config_ids),
                KnowledgeNode.kind == "workflow_config",
            )
            .order_by(KnowledgeNode.version.desc())
            .all()
        )
        return [_VersionProxy.from_node(n) for n in nodes]

    def _diff_configs(self, current: dict[str, Any], proposed: dict[str, Any], prefix: str = "") -> list[str]:
        changes: list[str] = []
        keys = sorted(set(current) | set(proposed))
        for key in keys:
            path = f"{prefix}.{key}" if prefix else key
            current_value = current.get(key)
            proposed_value = proposed.get(key)
            if isinstance(current_value, dict) and isinstance(proposed_value, dict):
                changes.extend(self._diff_configs(current_value, proposed_value, path))
            elif current_value != proposed_value:
                changes.append(f"{path}: {current_value!r} -> {proposed_value!r}")
        return changes
