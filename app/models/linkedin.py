import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.content import ContentQueue, Intent, Pillar, _enum_values


class LinkedInContentType(str, enum.Enum):
    THOUGHT_LEADERSHIP = "thought_leadership"
    DATA_INSIGHT = "data_insight"
    COMPANY_UPDATE = "company_update"


class LinkedInApprovalTier(str, enum.Enum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class LinkedInStatus(str, enum.Enum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PUBLISHING_UNKNOWN = "publishing_unknown"
    FAILED = "failed"
    REJECTED = "rejected"


class LinkedInPost(Base):
    """Queue record for a LinkedIn post draft/review/publish lifecycle."""

    __tablename__ = "linkedin_post"

    content_type_enum = Enum(
        LinkedInContentType,
        name="linkedin_content_type_enum",
        values_callable=_enum_values,
    )
    approval_tier_enum = Enum(
        LinkedInApprovalTier,
        name="linkedin_approval_tier_enum",
        values_callable=_enum_values,
    )
    status_enum = Enum(
        LinkedInStatus,
        name="linkedin_status_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[LinkedInContentType] = mapped_column(content_type_enum, nullable=False)
    pillar: Mapped[Pillar] = mapped_column(ContentQueue.pillar_enum, nullable=False)
    intent: Mapped[Intent] = mapped_column(ContentQueue.intent_enum, nullable=False)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    approval_tier: Mapped[LinkedInApprovalTier] = mapped_column(approval_tier_enum, nullable=False)
    status: Mapped[LinkedInStatus] = mapped_column(status_enum, nullable=False, default=LinkedInStatus.DRAFT)
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    compliance_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # External platform identifier returned by LinkedIn after publish.
    linkedin_post_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class LinkedInGenerationLog(Base):
    """Generation audit log for LinkedIn drafts."""

    __tablename__ = "linkedin_generation_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Internal FK-style reference to linkedin_post.id (UUID), not the external LinkedIn id.
    linkedin_post_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    prompt_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_estimate: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
