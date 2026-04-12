import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.workflow import Platform, _enum_values


class VideoBriefKind(str, enum.Enum):
    FOUNDER_RAW = "founder_raw"
    REEL_FROM_STATIC = "reel_from_static"
    TESTIMONIAL = "testimonial"
    PARTNER_CUTDOWN = "partner_cutdown"


class VideoBriefStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    BRIEFED = "briefed"
    ARCHIVED = "archived"


class VideoBrief(Base):
    __tablename__ = "video_briefs"

    kind_enum = Enum(VideoBriefKind, name="video_brief_kind_enum", values_callable=_enum_values)
    status_enum = Enum(VideoBriefStatus, name="video_brief_status_enum", values_callable=_enum_values)
    platform_enum = Enum(
        Platform,
        name="platform_enum",
        values_callable=_enum_values,
        create_type=False,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[VideoBriefKind] = mapped_column(kind_enum, nullable=False)
    platform: Mapped[Platform] = mapped_column(platform_enum, nullable=False)
    brief_format: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[VideoBriefStatus] = mapped_column(status_enum, nullable=False, default=VideoBriefStatus.DRAFT)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    script: Mapped[str] = mapped_column(Text, nullable=False)
    shot_list: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    motion_graphic_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    source_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True
    )
    trigger_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trigger_events.id"), nullable=True
    )
    content_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_jobs.id"), nullable=True
    )
    draft_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("draft_variants.id"), nullable=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
