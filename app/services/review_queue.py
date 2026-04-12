# app/services/review_queue.py
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.brain import EntityEdge, EntityNode, KnowledgeNode
from app.publishers import get_publisher
from app.publishers.blog_factory import get_blog_publisher
from app.publishers.instagram_factory import get_instagram_publisher
from app.services.brain_query import BrainQuery
from app.services.publishing_connection_service import PublishingConnectionService

logger = logging.getLogger(__name__)


# Valid state transitions: action -> (expected_from, target_state)
VALID_TRANSITIONS = {
    "post_now": ("review_required", "publishing"),
    "schedule": ("review_required", "scheduled"),
    "reject": ("review_required", "rejected"),
    "expire": ("review_required", "expired"),
    "pause": ("scheduled", "review_required"),
    "move_to_manual": ("scheduled", "review_required"),
}


class ReviewQueue:
    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)

    def list_manual(self, limit: int = 50) -> list[KnowledgeNode]:
        return self.bq.list_drafts_by_status("review_required", limit=limit)

    def list_automatic(self, limit: int = 50) -> list[KnowledgeNode]:
        return (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.kind == "draft",
                KnowledgeNode.status == "scheduled",
            )
            .order_by(KnowledgeNode.valid_from.asc())
            .limit(limit)
            .all()
        )

    def list_by_state(self, status: str, limit: int = 50) -> list[KnowledgeNode]:
        return self.bq.list_drafts_by_status(status, limit=limit)

    def get_draft_detail(self, draft_id: uuid.UUID) -> dict | None:
        draft = self.bq.get_knowledge_node(draft_id)
        if not draft:
            return None
        workflow = self.bq.get_workflow_for_draft(draft_id)
        return {"draft": draft, "workflow": workflow}

    def act(
        self,
        draft_id: uuid.UUID,
        action: str,
        actor: str,
        notes: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> KnowledgeNode:
        draft = self.bq.get_knowledge_node(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        if action not in VALID_TRANSITIONS:
            raise ValueError(f"Unknown action: {action}")

        expected_from, target_state = VALID_TRANSITIONS[action]
        if draft.status != expected_from:
            raise ValueError(
                f"Cannot {action} draft in state {draft.status}; "
                f"expected {expected_from}"
            )

        # Record the review action as a knowledge node
        review_node = self.bq.create_knowledge_node(
            kind="review_action",
            title=f"{action} by {actor}",
            content=notes,
            status="active",
            confidence=1.0,
            trust_score=1.0,
            metadata={
                "action": action,
                "actor": actor,
                "notes": notes,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            },
        )
        self.bq.create_edge(
            source_id=draft.id,
            target_id=review_node.id,
            source_type="knowledge",
            target_type="knowledge",
            relation="reviewed_by",
        )

        # Apply state transition
        draft.status = target_state

        if action == "schedule":
            if not scheduled_at:
                raise ValueError("scheduled_at is required for schedule action")
            draft.valid_from = scheduled_at

        if action == "post_now":
            self._publish_draft(draft, published_via="post_now")

        self.db.flush()
        return draft

    def publish_due_draft(self, draft_id: uuid.UUID, actor: str = "scheduler") -> KnowledgeNode:
        draft = self.bq.get_knowledge_node(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")
        if draft.status not in ("scheduled",):
            raise ValueError(f"Cannot publish due draft in state {draft.status}")

        published_via = (
            "automatic_workflow"
            if draft.metadata_.get("mode") == "automatic"
            else "scheduled_manual"
        )

        review_node = self.bq.create_knowledge_node(
            kind="review_action",
            title=f"post_now by {actor}",
            status="active",
            confidence=1.0,
            trust_score=1.0,
            metadata={"action": "post_now", "actor": actor, "notes": "Published by scheduler."},
        )
        self.bq.create_edge(
            source_id=draft.id,
            target_id=review_node.id,
            source_type="knowledge",
            target_type="knowledge",
            relation="reviewed_by",
        )

        draft.status = "publishing"
        self._publish_draft(draft, published_via=published_via)
        self.db.flush()
        return draft

    def _publish_draft(self, draft: KnowledgeNode, *, published_via: str | None = None) -> None:
        meta = dict(draft.metadata_)
        meta["publish_attempted_at"] = datetime.now(timezone.utc).isoformat()
        if published_via:
            meta["published_via"] = published_via

        platform = meta.get("platform", "")
        target = PublishingConnectionService(self.db).resolve_active_publish_target(platform)
        runtime_config = None
        if target is not None:
            runtime_config = {
                **dict(target.get("credentials") or {}),
                **dict(target.get("config") or {}),
            }

        if platform == "blog":
            # Look for linked blog_article knowledge node
            blog_edges = (
                self.db.query(EntityEdge)
                .filter(
                    EntityEdge.source_id == draft.id,
                    EntityEdge.relation == "has_article",
                )
                .all()
            )
            blog_node = None
            if blog_edges:
                blog_node = self.bq.get_knowledge_node(blog_edges[0].target_id)

            payload = dict(meta.get("compliance_result") or {})
            if blog_node:
                bm = blog_node.metadata_
                payload = {
                    "title": blog_node.title,
                    "slug": bm.get("slug", ""),
                    "meta_description": bm.get("meta_description", ""),
                    "body_html": bm.get("body_html", ""),
                    "target_keywords": bm.get("target_keywords", []),
                    "headings": bm.get("headings", []),
                    "audience": bm.get("audience", ""),
                    "topic": bm.get("topic", ""),
                    "angle": bm.get("angle"),
                    "excerpt": bm.get("excerpt"),
                }

            result = get_blog_publisher(runtime_config=runtime_config).publish_article(
                title=payload.get("title", ""),
                slug=payload.get("slug", ""),
                body_markdown=draft.content or "",
                body_html=payload.get("body_html", ""),
                meta_description=payload.get("meta_description", ""),
                target_keywords=payload.get("target_keywords", []),
                headings=payload.get("headings", []),
                audience=payload.get("audience", ""),
                topic=payload.get("topic", ""),
                angle=payload.get("angle"),
                excerpt=payload.get("excerpt"),
            )
            if result.success:
                draft.status = "active"
                meta["platform_post_id"] = result.article_id
                meta["post_url"] = result.url
                meta["published_at"] = (result.published_at or datetime.now(timezone.utc)).isoformat()
                meta.pop("failure_reason", None)
                if blog_node:
                    bm = dict(blog_node.metadata_)
                    bm["cms_provider"] = os.getenv("BLOG_PUBLISHER", "mock").lower()
                    bm["cms_article_id"] = result.article_id
                    bm["canonical_url"] = result.url
                    blog_node.status = "active"
                    blog_node.metadata_ = bm
                self._record_publication(draft, meta)
            else:
                draft.status = "failed"
                meta["failure_reason"] = result.error
                if blog_node:
                    blog_node.status = "failed"
                    bm = dict(blog_node.metadata_)
                    bm["failure_reason"] = result.error
                    blog_node.metadata_ = bm
            draft.metadata_ = meta
            return

        if platform == "instagram":
            from app.models.asset import Asset
            from app.services.instagram_pipeline import build_instagram_caption

            assets = (
                self.db.query(Asset)
                .filter(Asset.draft_variant_id == draft.id)
                .order_by(Asset.sort_order.asc())
                .all()
            )
            asset_urls = [a.url or a.storage_path for a in assets if a.url or a.storage_path]
            if not asset_urls:
                draft.status = "failed"
                meta["failure_reason"] = "Instagram draft requires rendered assets before publish"
                draft.metadata_ = meta
                return

            publish_mode = "feed"
            cr = meta.get("compliance_result")
            if isinstance(cr, dict):
                publish_mode = cr.get("publish_mode", publish_mode)
            hashtags = meta.get("hashtags", [])
            result = get_instagram_publisher(runtime_config=runtime_config).publish_post(
                build_instagram_caption(draft.content or "", hashtags),
                asset_urls,
                publish_mode=publish_mode,
            )
            if result.success:
                draft.status = "active"
                meta["platform_post_id"] = result.post_id
                meta["post_url"] = result.post_url
                meta["published_at"] = datetime.now(timezone.utc).isoformat()
                meta.pop("failure_reason", None)
                self._record_publication(draft, meta)
            else:
                draft.status = "failed"
                meta["failure_reason"] = result.error
            draft.metadata_ = meta
            return

        # Generic publisher (X, LinkedIn, Newsletter)
        publisher = get_publisher(platform=platform, runtime_config=runtime_config)
        publish_metadata = None
        if platform == "newsletter" and isinstance(meta.get("compliance_result"), dict):
            cr = meta["compliance_result"]
            publish_metadata = {
                "subject": cr.get("subject"),
                "preview_text": cr.get("preview_text"),
                "segment": cr.get("segment"),
                "body_html": cr.get("body_html"),
            }
        if publish_metadata is None:
            result = publisher.publish(draft.content or "")
        else:
            result = publisher.publish(draft.content or "", metadata=publish_metadata)

        if result.success:
            draft.status = "active"
            meta["platform_post_id"] = result.platform_post_id
            meta["post_url"] = result.post_url
            meta["published_at"] = datetime.now(timezone.utc).isoformat()
            meta.pop("failure_reason", None)
            self._record_publication(draft, meta)
        else:
            draft.status = "failed"
            meta["failure_reason"] = result.error
        draft.metadata_ = meta

    def _record_publication(self, draft: KnowledgeNode, meta: dict) -> None:
        pub_node = self.bq.create_knowledge_node(
            kind="metric",
            title=f"Publication: {draft.title}",
            status="active",
            confidence=1.0,
            trust_score=1.0,
            metadata={
                "metric_type": "publication",
                "platform": meta.get("platform"),
                "platform_post_id": meta.get("platform_post_id"),
                "post_url": meta.get("post_url"),
                "published_at": meta.get("published_at"),
            },
        )
        self.bq.create_edge(
            source_id=draft.id,
            target_id=pub_node.id,
            source_type="knowledge",
            target_type="knowledge",
            relation="published_as",
        )
