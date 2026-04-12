import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.workflow import _enum_values


class ScienceContentType(str, enum.Enum):
    ADVISOR_SPOTLIGHT = "advisor_spotlight"
    WHITE_PAPER_EXCERPT = "white_paper_excerpt"
    PEER_REVIEW_MILESTONE = "peer_review_milestone"


class ScienceContentStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW_READY = "review_ready"
    PUBLISHED = "published"
    FAILED = "failed"


class ScienceContentRecord(Base):
    __tablename__ = "science_content_records"

    science_content_type_enum = Enum(
        ScienceContentType,
        name="science_content_type_enum",
        values_callable=_enum_values,
    )
    science_content_status_enum = Enum(
        ScienceContentStatus,
        name="science_content_status_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    science_type: Mapped[ScienceContentType] = mapped_column(science_content_type_enum, nullable=False)
    status: Mapped[ScienceContentStatus] = mapped_column(
        science_content_status_enum,
        nullable=False,
        default=ScienceContentStatus.DRAFT,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="linkedin")
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True
    )
    workflow_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trigger_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trigger_events.id"), nullable=True
    )
    content_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_jobs.id"), nullable=True
    )
    draft_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("draft_variants.id"), nullable=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_notes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

