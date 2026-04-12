import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.workflow import Platform, _enum_values


class MemoryBucket(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"
    DRAFT = "draft"
    SOURCE = "source"


class MemorySourceKind(str, enum.Enum):
    DRAFT_VARIANT = "draft_variant"
    LEGACY_X = "legacy_x"
    LEGACY_LINKEDIN = "legacy_linkedin"
    LEGACY_INSTAGRAM = "legacy_instagram"
    CONTENT_BRAIN = "content_brain"
    TRIGGER_EVENT = "trigger_event"


class MemoryItem(Base):
    __tablename__ = "memory_items"

    __table_args__ = (
        UniqueConstraint("source_kind", "source_id", name="uq_memory_item_source"),
    )

    memory_bucket_enum = Enum(
        MemoryBucket,
        name="memory_bucket_enum",
        values_callable=_enum_values,
    )
    memory_source_kind_enum = Enum(
        MemorySourceKind,
        name="memory_source_kind_enum",
        values_callable=_enum_values,
    )
    platform_enum = Enum(
        Platform,
        name="platform_enum",
        values_callable=_enum_values,
        create_type=False,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_kind: Mapped[MemorySourceKind] = mapped_column(memory_source_kind_enum, nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    bucket: Mapped[MemoryBucket] = mapped_column(memory_bucket_enum, nullable=False)
    platform: Mapped[Platform | None] = mapped_column(platform_enum, nullable=True)
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True
    )
    workflow_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    draft_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("draft_variants.id"), nullable=True
    )
    trigger_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trigger_events.id"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class MemoryEmbedding(Base):
    __tablename__ = "memory_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    memory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_items.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="metadata_only")
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dimensions: Mapped[int | None] = mapped_column(nullable=True)
    embedding: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
