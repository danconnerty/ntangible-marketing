import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.workflow import _enum_values


class BlogArticleStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW_READY = "review_ready"
    PUBLISHED = "published"
    FAILED = "failed"


class BlogArticle(Base):
    __tablename__ = "blog_articles"

    blog_article_status_enum = Enum(
        BlogArticleStatus,
        name="blog_article_status_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    meta_description: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    target_keywords: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    headings: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[BlogArticleStatus] = mapped_column(
        blog_article_status_enum,
        nullable=False,
        default=BlogArticleStatus.DRAFT,
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True)
    trigger_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trigger_events.id"), nullable=True)
    content_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("content_jobs.id"), nullable=True)
    draft_variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("draft_variants.id"), nullable=True)
    cms_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cms_article_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
