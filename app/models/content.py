import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class ContentType(str, enum.Enum):
    HOT_TAKE = "hot_take"
    DATA_DROP = "data_drop"
    TREND_JACK = "trend_jack"


class Pillar(str, enum.Enum):
    BLIND_SPOT = "blind_spot"
    COST_OF_GUESSING = "cost_of_guessing"
    CLIENT_PROOF = "client_proof"
    THOUGHT_LEADERSHIP = "thought_leadership"
    PRODUCT = "product"


class Intent(str, enum.Enum):
    BRAND = "brand"
    PARTNER = "partner"
    REVENUE = "revenue"


class Status(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PUBLISHING_UNKNOWN = "publishing_unknown"
    FAILED = "failed"
    REJECTED = "rejected"


class ContentQueue(Base):
    __tablename__ = "content_queue"

    content_type_enum = Enum(
        ContentType,
        name="content_type_enum",
        values_callable=_enum_values,
    )
    pillar_enum = Enum(
        Pillar,
        name="pillar_enum",
        values_callable=_enum_values,
    )
    intent_enum = Enum(
        Intent,
        name="intent_enum",
        values_callable=_enum_values,
    )
    status_enum = Enum(
        Status,
        name="status_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[ContentType] = mapped_column(content_type_enum, nullable=False)
    pillar: Mapped[Pillar] = mapped_column(pillar_enum, nullable=False)
    intent: Mapped[Intent] = mapped_column(intent_enum, nullable=False)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    status: Mapped[Status] = mapped_column(status_enum, nullable=False, default=Status.DRAFT)
    variant_group: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tweet_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compliance_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    regeneration_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class GenerationLog(Base):
    __tablename__ = "generation_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_queue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    prompt_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_estimate: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
