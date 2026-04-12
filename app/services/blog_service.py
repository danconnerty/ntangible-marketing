from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.blog_compliance import run_blog_compliance_checks
from app.agents.blog_writer import generate_blog_draft
from app.models.blog import BlogArticle, BlogArticleStatus
from app.models.brain import EntityNode, KnowledgeNode
from app.publishers.blog_factory import get_blog_publisher
from app.schemas.workflow_config import WorkflowVersionConfig
from app.services.brain_query import BrainQuery
from app.services.publishing_connection_service import PublishingConnectionService
from app.services.review_queue import ReviewQueue
from app.services.workflow_engine import WorkflowEngine


class BlogService:
    def __init__(self, db: Session):
        self.db = db
        self.bq = BrainQuery(db)
        self.workflow_engine = WorkflowEngine(db)

    def list_dashboard(self, limit: int = 50) -> dict[str, Any]:
        articles = self._query_articles(limit=limit)
        return {
            "articles": [self._serialize_article(article) for article in articles],
            "counts": {
                "total": len(articles),
                "review_ready": sum(1 for article in articles if article.status == BlogArticleStatus.REVIEW_READY),
                "published": sum(1 for article in articles if article.status == BlogArticleStatus.PUBLISHED),
                "failed": sum(1 for article in articles if article.status == BlogArticleStatus.FAILED),
            },
        }

    def generate_draft(
        self,
        *,
        topic: str,
        audience: str,
        target_keywords: list[str] | None = None,
        angle: str | None = None,
        source_notes: list[str] | None = None,
    ) -> dict[str, Any]:
        workflow_entity = None
        trigger_node = None
        job_node = None
        draft_node = None
        workflow_failed = False
        request_text = self._build_request_text(
            topic=topic,
            audience=audience,
            target_keywords=target_keywords or [],
            angle=angle,
            source_notes=source_notes or [],
        )
        try:
            workflow_entity = self._resolve_workflow()
            trigger_node = self._create_trigger(request_text, workflow_entity, topic, audience, target_keywords, angle, source_notes)
            job_node = self._execute_workflow(trigger_node, workflow_entity)
            draft_node = self._latest_draft_for_job(getattr(job_node, "id", None))
        except Exception:
            workflow_failed = True

        article_payload = self._article_payload_from_draft(draft_node)
        if article_payload is None:
            article_payload = self._generate_article_payload(
                topic=topic,
                audience=audience,
                target_keywords=target_keywords or [],
                angle=angle,
                source_notes=source_notes or [],
            )

        if workflow_failed:
            status = BlogArticleStatus.REVIEW_READY if article_payload.get("passed", True) else BlogArticleStatus.FAILED
        else:
            status = self._article_status(job_node=job_node, draft_node=draft_node)

        workflow_entity_id = getattr(workflow_entity, "id", None)
        trigger_node_id = getattr(trigger_node, "id", None)
        job_node_id = getattr(job_node, "id", None)
        draft_node_id = getattr(draft_node, "id", None)

        article = BlogArticle(
            id=uuid.uuid4(),
            slug=article_payload["slug"],
            title=article_payload["title"],
            meta_description=article_payload["meta_description"],
            audience=article_payload["audience"],
            topic=article_payload["topic"],
            angle=article_payload["angle"],
            body_markdown=article_payload["body_markdown"],
            body_html=article_payload["body_html"],
            target_keywords=article_payload["target_keywords"],
            headings=article_payload["headings"],
            word_count=article_payload["word_count"],
            status=status,
            # Brain node IDs stored here during transition (no FK enforcement in tests / brain migration handles rename)
            workflow_id=workflow_entity_id,
            trigger_event_id=trigger_node_id,
            content_job_id=job_node_id,
            draft_variant_id=draft_node_id,
            publish_payload={
                "excerpt": article_payload.get("excerpt"),
                "source_notes": source_notes or [],
                "checks_run": article_payload.get("checks_run", []),
                "workflow_slug": getattr(workflow_entity, "slug", None),
                # Also store brain node IDs in payload for querying without FK
                "workflow_entity_id": str(workflow_entity_id) if workflow_entity_id else None,
                "trigger_node_id": str(trigger_node_id) if trigger_node_id else None,
                "job_node_id": str(job_node_id) if job_node_id else None,
                "draft_node_id": str(draft_node_id) if draft_node_id else None,
            },
            failure_reason=(
                article_payload.get("failure_reason")
                if workflow_failed
                else self._article_failure_reason(job_node=job_node, draft_node=draft_node)
            ),
        )
        self.db.add(article)
        self.db.flush()
        return self._serialize_article(article)

    def publish_article(
        self,
        article_id: str | uuid.UUID,
        *,
        actor: str = "editor",
        scheduled_at: datetime | None = None,
    ) -> dict[str, Any]:
        article = self._get_article(article_id)
        if article is None:
            raise ValueError(f"Blog article not found: {article_id}")

        # Check if we have a draft KnowledgeNode in review_required state
        draft_node_id = self._get_draft_node_id(article)
        if draft_node_id is not None:
            draft_node = self.bq.get_knowledge_node(draft_node_id)
            if draft_node is not None and draft_node.status == "review_required":
                # Attempt legacy ReviewQueue path if DraftVariant exists; otherwise promote directly
                try:
                    from app.models.review import DraftVariant, ReviewActionType
                    legacy_draft = self.db.query(DraftVariant).filter(DraftVariant.id == draft_node_id).first()
                    if legacy_draft is not None:
                        ReviewQueue(self.db).act(
                            legacy_draft.id,
                            action=ReviewActionType.POST_NOW,
                            actor=actor,
                        )
                        self.db.flush()
                        return self._serialize_article(article)
                except Exception:
                    pass

        optimized = self._apply_seo_normalization(article)
        target = PublishingConnectionService(self.db).resolve_active_publish_target("blog")
        runtime_config = None
        if target is not None:
            runtime_config = {
                **dict(target.get("credentials") or {}),
                **dict(target.get("config") or {}),
            }

        publisher = (
            get_blog_publisher(runtime_config=runtime_config)
            if runtime_config is not None
            else get_blog_publisher()
        )
        result = publisher.publish_article(
            title=article.title,
            slug=article.slug,
            body_markdown=optimized["body_markdown"],
            body_html=optimized["body_html"],
            meta_description=optimized["meta_description"],
            target_keywords=list(article.target_keywords or []),
            headings=list(article.headings or []),
            audience=article.audience,
            topic=article.topic,
            angle=article.angle,
            excerpt=(article.publish_payload or {}).get("excerpt"),
            scheduled_at=scheduled_at,
        )

        publish_payload = dict(article.publish_payload or {})
        publish_payload.update(
            {
                "last_publish_actor": actor,
                "last_publish_attempt_at": datetime.now(timezone.utc).isoformat(),
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            }
        )
        article.publish_payload = publish_payload

        if result.success:
            article.status = BlogArticleStatus.PUBLISHED
            article.cms_provider = (
                (runtime_config or {}).get("provider_key")
                or os.getenv("BLOG_PUBLISHER", "mock").lower()
            )
            article.cms_article_id = result.article_id
            article.canonical_url = result.url
            article.failure_reason = None
            article.published_at = result.published_at or datetime.now(timezone.utc)
        else:
            article.status = BlogArticleStatus.FAILED
            article.failure_reason = result.error or "Blog publish failed"

        self.db.flush()
        return self._serialize_article(article)

    def _resolve_workflow(self) -> EntityNode:
        """Resolve or create the blog-authority-engine workflow EntityNode."""
        slug = "blog-authority-engine"
        workflow_entity = self.bq.get_entity_by_slug("workflow", slug)
        if workflow_entity is not None:
            return workflow_entity

        workflow_entity = self.bq.create_entity(
            entity_type="workflow",
            canonical_name="Blog Authority Engine",
            slug=slug,
            status="active",
            description="Manual-first long-form blog workflow.",
            metadata={
                "platform": "blog",
                "content_type": "blog_article",
                "mode": "manual",
            },
        )

        config_node = self.bq.create_knowledge_node(
            kind="workflow_config",
            title=f"Config: {slug}",
            status="active",
            confidence=1.0,
            trust_score=1.0,
            metadata={
                "workflow_entity_id": str(workflow_entity.id),
                "version_number": 1,
                "version_note": "Bootstrapped blog workflow",
                "author": "system",
                "config": WorkflowVersionConfig(
                    prompt={
                        "tone_notes": "Write with practical authority, evidence, and zero corporate filler.",
                        "system_prompt_additions": "Produce a structured blog draft that can be published after review.",
                    },
                    formatting={
                        "max_chars": 12000,
                    },
                    routing={
                        "target_content_type": "blog_article",
                        "target_intent": "brand",
                        "target_pillar": "thought_leadership",
                    },
                ).model_dump(),
            },
        )
        self.bq.create_edge(
            source_id=workflow_entity.id,
            target_id=config_node.id,
            source_type="entity",
            target_type="knowledge",
            relation="has_config",
        )
        return workflow_entity

    def _create_trigger(
        self,
        request_text: str,
        workflow_entity: EntityNode,
        topic: str,
        audience: str,
        target_keywords: list[str] | None,
        angle: str | None,
        source_notes: list[str] | None,
    ) -> KnowledgeNode:
        """Create a manual trigger KnowledgeNode for a blog draft request."""
        trigger_node = self.bq.create_knowledge_node(
            kind="trigger",
            title=f"Manual trigger: {request_text[:60]}",
            status="active",
            confidence=1.0,
            trust_score=1.0,
            metadata={
                "trigger_type": "manual",
                "request": request_text,
                "workflow_entity_id": str(workflow_entity.id),
                "blog_context": {
                    "topic": topic,
                    "audience": audience,
                    "target_keywords": target_keywords or [],
                    "angle": angle,
                    "source_notes": source_notes or [],
                },
            },
        )
        return trigger_node

    def _execute_workflow(
        self,
        trigger_node: KnowledgeNode,
        workflow_entity: EntityNode,
    ) -> KnowledgeNode:
        """Execute workflow via WorkflowEngine.execute_brain and return a job KnowledgeNode."""
        return self.workflow_engine.execute_brain(trigger_node)

    def _build_request_text(
        self,
        *,
        topic: str,
        audience: str,
        target_keywords: list[str],
        angle: str | None,
        source_notes: list[str],
    ) -> str:
        lines = [
            f"Blog topic: {topic}",
            f"Audience: {audience}",
        ]
        if target_keywords:
            lines.append(f"Target keywords: {', '.join(target_keywords)}")
        if angle:
            lines.append(f"Angle: {angle}")
        if source_notes:
            lines.append("Source notes:")
            lines.extend(f"- {note}" for note in source_notes)
        lines.append("Write an evidence-led 800-1200 word article with title, meta description, headings, and CTA.")
        return "\n".join(lines)

    def _latest_draft_for_job(self, job_id: uuid.UUID | None) -> KnowledgeNode | None:
        """Return the first draft KnowledgeNode produced by job_id."""
        if job_id is None:
            return None
        try:
            # Find a produced_draft edge from this job node
            from app.models.brain import EntityEdge
            edge = (
                self.db.query(EntityEdge)
                .filter(
                    EntityEdge.source_id == job_id,
                    EntityEdge.relation == "produced_draft",
                )
                .first()
            )
            if edge is None:
                return None
            return self.bq.get_knowledge_node(edge.target_id)
        except Exception:
            return None

    def _article_payload_from_draft(self, draft_node: KnowledgeNode | None) -> dict[str, Any] | None:
        if draft_node is None:
            return None
        meta = draft_node.metadata_ or {}
        compliance = meta.get("compliance_result") or {}
        if not isinstance(compliance, dict):
            return None
        required = ("title", "slug", "meta_description", "body_html", "target_keywords", "headings", "audience", "topic")
        if any(compliance.get(key) in (None, "", []) for key in required):
            return None
        return {
            "slug": compliance["slug"],
            "title": compliance["title"],
            "meta_description": compliance["meta_description"],
            "audience": compliance["audience"],
            "topic": compliance["topic"],
            "angle": compliance.get("angle"),
            "body_markdown": draft_node.content or "",
            "body_html": compliance["body_html"],
            "target_keywords": list(compliance.get("target_keywords") or []),
            "headings": list(compliance.get("headings") or []),
            "word_count": compliance.get("word_count") or len((draft_node.content or "").split()),
            "excerpt": compliance.get("excerpt"),
            "checks_run": list(compliance.get("checks_run") or []),
        }

    def _generate_article_payload(
        self,
        *,
        topic: str,
        audience: str,
        target_keywords: list[str],
        angle: str | None,
        source_notes: list[str],
    ) -> dict[str, Any]:
        generated = generate_blog_draft(
            topic=topic,
            audience=audience,
            target_keywords=target_keywords,
            angle=angle,
            source_notes=source_notes,
        )
        compliance = run_blog_compliance_checks(generated)
        return {
            "slug": generated["slug"],
            "title": generated["title"],
            "meta_description": generated["meta_description"],
            "audience": generated["audience"],
            "topic": generated["topic"],
            "angle": generated["angle"],
            "body_markdown": compliance.corrected_body_markdown or generated["body_markdown"],
            "body_html": generated["body_html"],
            "target_keywords": generated["target_keywords"],
            "headings": generated["headings"],
            "word_count": generated["word_count"],
            "excerpt": generated.get("excerpt"),
            "checks_run": compliance.checks_run,
            "failure_reason": compliance.failure_reason,
            "passed": compliance.passed,
        }

    def _article_status(
        self,
        *,
        job_node: KnowledgeNode | None,
        draft_node: KnowledgeNode | None,
    ) -> BlogArticleStatus:
        job_status = getattr(job_node, "status", "failed") if job_node is not None else "failed"
        draft_status = getattr(draft_node, "status", None) if draft_node is not None else None
        if job_status == "completed" and draft_node is not None and draft_status != "failed":
            return BlogArticleStatus.REVIEW_READY
        return BlogArticleStatus.FAILED

    def _article_failure_reason(
        self,
        *,
        job_node: KnowledgeNode | None,
        draft_node: KnowledgeNode | None,
    ) -> str | None:
        job_status = getattr(job_node, "status", "failed") if job_node is not None else "failed"
        if job_status == "completed":
            if draft_node is not None:
                return (draft_node.metadata_ or {}).get("failure_reason")
            return None
        if draft_node is not None:
            return (draft_node.metadata_ or {}).get("failure_reason") or "Blog workflow failed"
        return "Blog workflow failed"

    def _get_draft_node_id(self, article: BlogArticle) -> uuid.UUID | None:
        """Extract draft node UUID from article, checking publish_payload first."""
        # Check publish_payload for brain node ID
        payload = article.publish_payload or {}
        draft_node_id_str = payload.get("draft_node_id")
        if draft_node_id_str:
            try:
                return uuid.UUID(str(draft_node_id_str))
            except ValueError:
                pass
        # Fall back to draft_variant_id field
        if getattr(article, "draft_variant_id", None):
            try:
                return uuid.UUID(str(article.draft_variant_id))
            except (ValueError, AttributeError):
                pass
        return None

    def optimize_seo(self, post_id: str | uuid.UUID) -> dict[str, Any]:
        article = self._get_article(post_id)
        if article is None:
            raise ValueError(f"Blog article not found: {post_id}")

        optimized = self._apply_seo_normalization(article)
        article.meta_description = optimized["meta_description"]
        article.body_markdown = optimized["body_markdown"]
        article.body_html = optimized["body_html"]
        article.word_count = optimized["word_count"]
        self.db.flush()
        return self._serialize_article(article)

    def _apply_seo_normalization(self, article: BlogArticle) -> dict[str, Any]:
        keywords = [keyword.strip() for keyword in article.target_keywords or [] if keyword and keyword.strip()]
        primary_keyword = keywords[0] if keywords else article.topic

        meta_description = (article.meta_description or "").strip()
        if primary_keyword.lower() not in meta_description.lower():
            meta_description = f"{meta_description.rstrip('.')} {primary_keyword}.".strip()
        if len(meta_description) > 170:
            meta_description = meta_description[:167].rstrip() + "..."

        body_markdown = article.body_markdown
        if "CTA:" not in body_markdown:
            body_markdown = (
                f"{body_markdown}\n\nCTA: Start with one use case where {primary_keyword} clarifies the next decision."
            )

        body_html = article.body_html
        if "CTA:" not in body_html and "</p>" in body_html:
            body_html = (
                f"{body_html}\n<p>CTA: Start with one use case where {primary_keyword} clarifies the next decision.</p>"
            )

        word_count = len(body_markdown.split())
        return {
            "meta_description": meta_description,
            "body_markdown": body_markdown,
            "body_html": body_html,
            "word_count": word_count,
        }

    def _get_article(self, article_id: str | uuid.UUID) -> BlogArticle | None:
        try:
            article_uuid = article_id if isinstance(article_id, uuid.UUID) else uuid.UUID(str(article_id))
        except ValueError:
            return None

        try:
            return self.db.query(BlogArticle).filter(BlogArticle.id == article_uuid).first()
        except Exception:
            for item in getattr(self.db, "added", []):
                if isinstance(item, BlogArticle) and item.id == article_uuid:
                    return item
            return None

    def _query_articles(self, *, limit: int) -> list[BlogArticle]:
        try:
            return (
                self.db.query(BlogArticle)
                .order_by(BlogArticle.created_at.desc())
                .limit(limit)
                .all()
            )
        except Exception:
            added = [item for item in getattr(self.db, "added", []) if isinstance(item, BlogArticle)]
            return list(reversed(added))[:limit]

    def _serialize_article(self, article: BlogArticle) -> dict[str, Any]:
        payload = article.publish_payload or {}
        return {
            "id": str(article.id),
            "slug": article.slug,
            "title": article.title,
            "meta_description": article.meta_description,
            "audience": article.audience,
            "topic": article.topic,
            "angle": article.angle,
            "body_markdown": article.body_markdown,
            "body_html": article.body_html,
            "target_keywords": list(article.target_keywords or []),
            "headings": list(article.headings or []),
            "word_count": getattr(article, "word_count", len((article.body_markdown or "").split())),
            "status": article.status.value,
            "cms_provider": article.cms_provider,
            "cms_article_id": article.cms_article_id,
            "canonical_url": article.canonical_url,
            "publish_payload": payload,
            "failure_reason": article.failure_reason,
            "workflow_id": str(article.workflow_id) if getattr(article, "workflow_id", None) else None,
            "trigger_event_id": str(article.trigger_event_id) if getattr(article, "trigger_event_id", None) else None,
            "content_job_id": str(article.content_job_id) if getattr(article, "content_job_id", None) else None,
            "draft_variant_id": str(article.draft_variant_id) if getattr(article, "draft_variant_id", None) else None,
            "workflow_slug": payload.get("workflow_slug") or self._workflow_slug_for_entity(getattr(article, "workflow_id", None)),
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "created_at": article.created_at.isoformat() if getattr(article, "created_at", None) else None,
        }

    def _workflow_slug_for_entity(self, entity_id: uuid.UUID | None) -> str | None:
        if entity_id is None:
            return None
        try:
            entity = self.bq.get_entity(entity_id)
        except Exception:
            return None
        return entity.slug if entity is not None else None
