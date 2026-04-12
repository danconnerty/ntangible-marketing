import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.workflow import _enum_values


class UGCRequestStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    ARCHIVED = "archived"


class UGCSubmissionStatus(str, enum.Enum):
    RECEIVED = "received"
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class UGCTestimonialRequest(Base):
    __tablename__ = "ugc_testimonial_requests"

    status_enum = Enum(UGCRequestStatus, name="ugc_request_status_enum", values_callable=_enum_values)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_name: Mapped[str] = mapped_column(String(255), nullable=False)
    athlete_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    score_tier: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    preview_text: Mapped[str] = mapped_column(Text, nullable=False)
    request_copy: Mapped[str] = mapped_column(Text, nullable=False)
    graphic_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    graphic_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[UGCRequestStatus] = mapped_column(status_enum, nullable=False, default=UGCRequestStatus.DRAFT)
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
    video_brief_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_briefs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class UGCSubmission(Base):
    __tablename__ = "ugc_submissions"

    status_enum = Enum(UGCSubmissionStatus, name="ugc_submission_status_enum", values_callable=_enum_values)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    testimonial_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ugc_testimonial_requests.id"), nullable=True
    )
    athlete_name: Mapped[str] = mapped_column(String(255), nullable=False)
    athlete_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    athlete_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consent_athlete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_parent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_share: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    score_tier: Mapped[str] = mapped_column(String(64), nullable=False)
    video_url: Mapped[str] = mapped_column(Text, nullable=False)
    testimonial_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[UGCSubmissionStatus] = mapped_column(
        status_enum,
        nullable=False,
        default=UGCSubmissionStatus.RECEIVED,
    )
    shareable_score_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    graphic_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    graphic_url: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    video_brief_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("video_briefs.id"), nullable=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
