import re
import uuid
from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.models.brain import KnowledgeNode
from app.models.content import ContentQueue, Status
from app.models.content_brain import ContentBrainItem
from app.models.linkedin import LinkedInPost, LinkedInStatus
from app.models.review import ContentJob, DraftVariant
from app.models.trigger import TriggerEvent
from app.models.workflow import DraftState, Platform, Workflow
from app.services.brain_query import BrainQuery


TOKEN_RE = re.compile(r"[a-z0-9]{3,}")

# Observation kinds (active/draft content derived from drafts)
OBSERVATION_STATES = {DraftState.PUBLISHED, DraftState.REJECTED, DraftState.EXPIRED, DraftState.FAILED}

# Status-to-brain-status mapping
DRAFT_STATE_TO_STATUS = {
    DraftState.PUBLISHED: "approved",
    DraftState.REJECTED: "rejected",
    DraftState.EXPIRED: "expired",
    DraftState.FAILED: "failed",
}


class MemoryRetrievalService:
    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)

    def sync_control_room_memory(self, limit: int = 500) -> int:
        drafts = (
            self.db.query(DraftVariant)
            .order_by(DraftVariant.created_at.desc())
            .limit(limit)
            .all()
        )
        if not drafts:
            return 0

        job_ids = [draft.content_job_id for draft in drafts]
        jobs = (
            self.db.query(ContentJob)
            .filter(ContentJob.id.in_(job_ids))
            .all()
        )
        jobs_by_id = {job.id: job for job in jobs}

        workflow_ids = [job.workflow_id for job in jobs]
        trigger_ids = [job.trigger_event_id for job in jobs]
        workflows = (
            self.db.query(Workflow)
            .filter(Workflow.id.in_(workflow_ids))
            .all()
            if workflow_ids
            else []
        )
        triggers = (
            self.db.query(TriggerEvent)
            .filter(TriggerEvent.id.in_(trigger_ids))
            .all()
            if trigger_ids
            else []
        )
        workflows_by_id = {workflow.id: workflow for workflow in workflows}
        triggers_by_id = {trigger.id: trigger for trigger in triggers}

        created_or_updated = 0
        for draft in drafts:
            job = jobs_by_id.get(draft.content_job_id)
            workflow = workflows_by_id.get(job.workflow_id) if job else None
            trigger = triggers_by_id.get(job.trigger_event_id) if job else None
            status = self._status_for_draft_state(draft.state)
            # Use observation kind for active memory derived from drafts
            kind = "observation"
            title = self._title_for_draft(draft, workflow)
            metadata = {
                "source_kind": "draft_variant",
                "source_id": str(draft.id),
                "draft_state": draft.state.value if draft.state else None,
                "platform": draft.platform.value if draft.platform else None,
                "workflow_slug": workflow.slug if workflow else None,
                "workflow_id": str(workflow.id) if workflow else None,
                "draft_variant_id": str(draft.id),
                "trigger_event_id": str(trigger.id) if trigger else None,
                "trigger_payload": trigger.source_payload if trigger else {},
                "hashtags": draft.hashtags or [],
                "failure_reason": draft.failure_reason,
                "compliance_result": draft.compliance_result or {},
                "segment": (draft.compliance_result or {}).get("segment"),
                "subject": (draft.compliance_result or {}).get("subject"),
                "preview_text": (draft.compliance_result or {}).get("preview_text"),
            }
            search_text = " ".join(
                part
                for part in [
                    title or "",
                    draft.content or "",
                    " ".join(draft.hashtags or []),
                    workflow.name if workflow else "",
                    workflow.slug if workflow else "",
                    (draft.compliance_result or {}).get("subject", ""),
                    (draft.compliance_result or {}).get("preview_text", ""),
                    (draft.compliance_result or {}).get("segment", ""),
                    self._flatten_payload(trigger.source_payload if trigger else {}),
                ]
                if part
            )
            created_or_updated += self._upsert_memory_item(
                source_kind="draft_variant",
                source_id=str(draft.id),
                kind=kind,
                status=status,
                platform=draft.platform,
                workflow=workflow,
                draft=draft,
                trigger=trigger,
                title=title,
                content=draft.content,
                search_text=search_text,
                metadata=metadata,
            )

        created_or_updated += self.sync_legacy_memory(limit=limit)
        self.db.flush()
        return created_or_updated

    def sync_legacy_memory(self, limit: int = 250) -> int:
        count = 0

        x_items = (
            self.db.query(ContentQueue)
            .order_by(ContentQueue.created_at.desc())
            .limit(limit)
            .all()
        )
        for item in x_items:
            status = "approved" if item.status == Status.PUBLISHED else "failed" if item.status == Status.FAILED else "draft"
            count += self._upsert_memory_item(
                source_kind="legacy_x",
                source_id=str(item.id),
                kind="observation",
                status=status,
                platform=Platform.X,
                workflow=None,
                draft=None,
                trigger=None,
                title=f"Legacy X {item.content_type.value}",
                content=item.content,
                search_text=" ".join(
                    filter(None, [item.content, " ".join(item.hashtags or []), item.pillar.value, item.intent.value])
                ),
                metadata={
                    "source_kind": "legacy_x",
                    "source_id": str(item.id),
                    "platform": Platform.X.value,
                    "legacy_status": item.status.value,
                    "pillar": item.pillar.value,
                    "intent": item.intent.value,
                    "post_url": item.post_url,
                },
            )

        linkedin_items = (
            self.db.query(LinkedInPost)
            .order_by(LinkedInPost.created_at.desc())
            .limit(limit)
            .all()
        )
        for item in linkedin_items:
            status = "approved" if item.status == LinkedInStatus.PUBLISHED else "rejected" if item.status == LinkedInStatus.REJECTED else "draft"
            count += self._upsert_memory_item(
                source_kind="legacy_linkedin",
                source_id=str(item.id),
                kind="observation",
                status=status,
                platform=Platform.LINKEDIN,
                workflow=None,
                draft=None,
                trigger=None,
                title=f"Legacy LinkedIn {item.content_type.value}",
                content=item.content,
                search_text=" ".join(
                    filter(None, [item.content, " ".join(item.hashtags or []), item.pillar.value, item.intent.value])
                ),
                metadata={
                    "source_kind": "legacy_linkedin",
                    "source_id": str(item.id),
                    "platform": Platform.LINKEDIN.value,
                    "legacy_status": item.status.value,
                    "approval_tier": item.approval_tier.value,
                    "post_url": item.post_url,
                },
            )

        public_items = (
            self.db.query(ContentBrainItem)
            .order_by(ContentBrainItem.published_at.desc().nullslast(), ContentBrainItem.created_at.desc())
            .limit(limit)
            .all()
        )
        for item in public_items:
            platform_value = item.platform.value if item.platform and item.platform.value in {member.value for member in Platform} else None
            platform = Platform(platform_value) if platform_value else None
            count += self._upsert_memory_item(
                source_kind="content_brain",
                source_id=str(item.id),
                kind="reference_content",
                status="active",
                platform=platform,
                workflow=None,
                draft=None,
                trigger=None,
                title=item.title,
                content=item.body_text or item.summary or item.title or "",
                search_text=" ".join(filter(None, [item.title or "", item.body_text or "", item.author or ""])),
                metadata={
                    "source_kind": "content_brain",
                    "source_id": str(item.id),
                    "platform": platform_value,
                    "source_url": item.url,
                    "author": item.author,
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                },
            )
        return count

    def search(
        self,
        *,
        query: str = "",
        platform: Platform | None = None,
        bucket: Any | None = None,  # kept for backwards compat; maps to status
        workflow_slug: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query_tokens = self._tokenize(query)
        items = self._load_candidate_items(limit=max(limit * 10, 100))
        scored: list[tuple[float, KnowledgeNode]] = []

        # Map legacy MemoryBucket to status string if needed
        bucket_status = bucket.value if bucket is not None and hasattr(bucket, "value") else bucket

        for item in items:
            item_meta = item.metadata_ or {}
            item_platform_str = item_meta.get("platform")
            item_workflow_slug = item_meta.get("workflow_slug")

            if bucket_status and item.status != bucket_status:
                continue
            if platform and item_platform_str != platform.value:
                continue
            if workflow_slug and item_workflow_slug != workflow_slug:
                continue
            score = self._score_item(item, query_tokens, platform, bucket_status, workflow_slug)
            if query_tokens and score <= 0:
                continue
            if not query_tokens and score <= 0:
                score = 1
            scored.append((score, item))

        scored.sort(
            key=lambda value: (
                value[0],
                value[1].created_at,
            ),
            reverse=True,
        )
        return [self._serialize_item(item, score) for score, item in scored[:limit]]

    def build_generation_context(
        self,
        *,
        query: str,
        platform: Platform,
        workflow_slug: str | None = None,
        approved_limit: int = 5,
        rejected_limit: int = 2,
        facts_limit: int = 5,
    ) -> dict[str, Any]:
        # Use string "approved"/"rejected" as bucket values
        approved = self.search(
            query=query,
            platform=platform,
            bucket=_BucketCompat("approved"),
            workflow_slug=workflow_slug,
            limit=approved_limit,
        )
        rejected = self.search(
            query=query,
            platform=platform,
            bucket=_BucketCompat("rejected"),
            workflow_slug=workflow_slug,
            limit=rejected_limit,
        )
        brain_facts = self._search_brain_facts(query=query, limit=facts_limit)
        memory_ids = [item["id"] for item in approved + rejected + brain_facts]
        return {
            "approved_examples": approved,
            "rejected_examples": rejected,
            "brain_facts": brain_facts,
            "memory_ids": memory_ids,
        }

    def _search_brain_facts(self, *, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search fact nodes by keyword relevance. No bucket/platform filtering."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        facts = self.bq.list_knowledge_by_kind("fact", limit=250)
        scored: list[tuple[float, KnowledgeNode]] = []
        for item in facts:
            score = self._score_item(item, query_tokens, None, None, None)
            if score > 0:
                scored.append((score, item))
        scored.sort(
            key=lambda value: (
                value[0],
                value[1].created_at,
            ),
            reverse=True,
        )
        return [self._serialize_item(item, score) for score, item in scored[:limit]]

    def _load_candidate_items(self, limit: int = 250) -> list[KnowledgeNode]:
        obs = self.bq.list_knowledge_by_kind("observation", limit=limit)
        ref = self.bq.list_knowledge_by_kind("reference_content", limit=limit)
        combined = obs + ref
        # Sort by created_at descending
        combined.sort(key=lambda n: n.created_at, reverse=True)
        return combined[:limit]

    def _upsert_memory_item(
        self,
        *,
        source_kind: str,
        source_id: str,
        kind: str,
        status: str,
        platform: Platform | None,
        workflow: Workflow | None,
        draft: DraftVariant | None,
        trigger: TriggerEvent | None,
        title: str | None,
        content: str,
        search_text: str,
        metadata: dict[str, Any] | None,
    ) -> int:
        # Check for existing node with same source_kind + source_id
        all_nodes = self.bq.list_knowledge_by_kind(kind, limit=10000)
        for node in all_nodes:
            meta = node.metadata_ or {}
            if meta.get("source_kind") == source_kind and meta.get("source_id") == source_id:
                # Update existing
                node.status = status
                node.title = title
                node.content = content
                node.metadata_ = {**(metadata or {}), "search_text": search_text}
                self.db.flush()
                return 1

        self.bq.create_knowledge_node(
            kind=kind,
            title=title or "Memory item",
            content=content,
            status=status,
            metadata={**(metadata or {}), "search_text": search_text},
        )
        return 1

    def _score_item(
        self,
        item: KnowledgeNode,
        query_tokens: set[str],
        platform: Platform | None,
        bucket_status: str | None,
        workflow_slug: str | None,
    ) -> float:
        meta = item.metadata_ or {}
        item_search_text = meta.get("search_text") or item.content or ""
        item_platform_str = meta.get("platform")
        item_workflow_slug = meta.get("workflow_slug")
        item_hashtags = meta.get("hashtags") or []

        score = 0.0
        text_tokens = self._tokenize(item_search_text)
        overlap = len(query_tokens & text_tokens)
        score += overlap * 5.0
        if query_tokens and " ".join(sorted(query_tokens)) in item_search_text.lower():
            score += 2.0
        if platform and item_platform_str == platform.value:
            score += 3.0
        if bucket_status and item.status == bucket_status:
            score += 2.0
        if workflow_slug and item_workflow_slug == workflow_slug:
            score += 4.0
        if item.status == "approved":
            score += 1.0
        score += len(query_tokens & self._tokenize(" ".join(item_hashtags))) * 2.0
        return score

    def _serialize_item(self, item: KnowledgeNode, score: float) -> dict[str, Any]:
        meta = item.metadata_ or {}
        platform_str = meta.get("platform")
        return {
            "id": str(item.id),
            "title": item.title,
            "content": item.content or "",
            "bucket": item.status,
            "platform": platform_str,
            "workflow_slug": meta.get("workflow_slug"),
            "metadata": meta,
            "recorded_at": item.created_at.isoformat() if item.created_at else None,
            "score": round(score, 2),
        }

    def _tokenize(self, value: str | None) -> set[str]:
        if not value:
            return set()
        return set(TOKEN_RE.findall(value.lower()))

    def _flatten_payload(self, payload: dict[str, Any]) -> str:
        values: list[str] = []
        for value in payload.values():
            if isinstance(value, dict):
                values.append(self._flatten_payload(value))
            elif isinstance(value, list):
                values.extend(str(item) for item in value)
            elif value is not None:
                values.append(str(value))
        return " ".join(values)

    def _title_for_draft(self, draft: DraftVariant, workflow: Workflow | None) -> str:
        label = workflow.name if workflow else "Workflow draft"
        return f"{label} ({draft.platform.value})"

    def _status_for_draft_state(self, state: DraftState | None) -> str:
        return DRAFT_STATE_TO_STATUS.get(state, "draft")


class _BucketCompat:
    """Tiny shim so callers can pass MemoryBucket-style objects or plain strings."""

    def __init__(self, value: str):
        self.value = value
