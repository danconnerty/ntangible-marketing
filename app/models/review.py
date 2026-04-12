import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.workflow import DraftState, Platform, _enum_values


class ReviewActionType(str, enum.Enum):
    POST_NOW = "post_now"
    SCHEDULE = "schedule"
    REJECT = "reject"
    EXPIRE = "expire"
    PAUSE = "pause"
    MOVE_TO_MANUAL = "move_to_manual"


class ContentJob(Base):
    __tablename__ = "content_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    workflow_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_versions.id"), nullable=False
    )
    trigger_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trigger_events.id"), nullable=False
    )
    prompt_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    retrieved_memory_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    compliance_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class DraftVariant(Base):
    __tablename__ = "draft_variants"

    platform_enum = Enum(
        Platform,
        name="platform_enum",
        values_callable=_enum_values,
        create_type=False,
    )
    draft_state_enum = Enum(
        DraftState,
        name="draft_state_enum",
        values_callable=_enum_values,
        create_type=False,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_jobs.id"), nullable=False
    )
    platform: Mapped[Platform] = mapped_column(platform_enum, nullable=False)
    intent: Mapped[str] = mapped_column(String(32), nullable=False, default="brand")
    partner_slug: Mapped[str | None] = mapped_column(String(128), nullable=True)
    partner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    state: Mapped[DraftState] = mapped_column(draft_state_enum, nullable=False, default=DraftState.GENERATED)
    recommended_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/New_York")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    compliance_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    platform_post_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_via: Mapped[str | None] = mapped_column(String(32), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ReviewAction(Base):
    __tablename__ = "review_actions"

    review_action_type_enum = Enum(
        ReviewActionType,
        name="review_action_type_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("draft_variants.id"), nullable=False
    )
    action: Mapped[ReviewActionType] = mapped_column(review_action_type_enum, nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
