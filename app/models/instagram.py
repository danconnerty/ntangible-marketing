import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class InstagramContentType(str, enum.Enum):
    ATHLETE_SPOTLIGHT = "athlete_spotlight"
    EDUCATION_CAROUSEL = "education_carousel"
    REEL = "reel"
    PARTNER_CONTENT = "partner_content"
    STORY = "story"
    STAT_CARD = "stat_card"


class InstagramTemplateFamily(str, enum.Enum):
    ATHLETE_SPOTLIGHT = "athlete_spotlight"
    COMMITMENT_POST = "commitment_post"
    CLUTCH_CERTIFIED = "clutch_certified"
    EVENT_LEADERBOARD = "event_leaderboard"
    BOLD_STATEMENT = "bold_statement"
    EDUCATION_CAROUSEL = "education_carousel"
    STORY_POLL = "story_poll"
    STORY_REPOST = "story_repost"
    PARTNER_EVENT_SPOTLIGHT = "partner_event_spotlight"


class InstagramRenderStatus(str, enum.Enum):
    PENDING = "pending"
    RENDERING = "rendering"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NEEDS_DESIGN_REVIEW = "needs_design_review"


class PartnerPackageStatus(str, enum.Enum):
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    FAILED = "failed"


class PartnerDeliveryChannel(str, enum.Enum):
    DASHBOARD = "dashboard"
    EMAIL = "email"
    EXPORT = "export"


class InstagramGenerationLog(Base):
    __tablename__ = "instagram_generation_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("draft_variants.id"),
        nullable=False,
    )
    prompt_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_estimate: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InstagramRenderJob(Base):
    __tablename__ = "instagram_render_jobs"

    template_family_enum = Enum(
        InstagramTemplateFamily,
        name="instagram_template_family_enum",
        values_callable=_enum_values,
    )
    render_status_enum = Enum(
        InstagramRenderStatus,
        name="instagram_render_status_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("draft_variants.id"),
        nullable=False,
    )
    template_family: Mapped[InstagramTemplateFamily] = mapped_column(template_family_enum, nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[InstagramRenderStatus] = mapped_column(
        render_status_enum,
        nullable=False,
        default=InstagramRenderStatus.PENDING,
    )
    provider_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PartnerDeliveryPackage(Base):
    __tablename__ = "partner_delivery_packages"

    package_status_enum = Enum(
        PartnerPackageStatus,
        name="partner_package_status_enum",
        values_callable=_enum_values,
    )
    delivery_channel_enum = Enum(
        PartnerDeliveryChannel,
        name="partner_delivery_channel_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("draft_variants.id"),
        nullable=False,
    )
    partner_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[PartnerPackageStatus] = mapped_column(
        package_status_enum,
        nullable=False,
        default=PartnerPackageStatus.NEEDS_REVIEW,
    )
    delivery_channel: Mapped[PartnerDeliveryChannel] = mapped_column(delivery_channel_enum, nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    asset_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    delivery_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
