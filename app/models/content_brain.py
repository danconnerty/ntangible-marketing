import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.content import _enum_values


class ContentSourceKind(str, enum.Enum):
    WEBSITE = "website"
    PARTNER_PAGE = "partner_page"
    WAYBACK = "wayback"
    FEED = "feed"
    SOCIAL = "social"
    EXTERNAL = "external"


class ContentPlatform(str, enum.Enum):
    WEB = "web"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    LINKEDIN = "linkedin"
    OTHER = "other"


class SnapshotFormat(str, enum.Enum):
    HTML = "html"
    XML = "xml"
    JSON = "json"
    TEXT = "text"


class ContentSourceTarget(Base):
    __tablename__ = "content_source_target"

    source_kind_enum = Enum(
        ContentSourceKind,
        name="content_source_kind_enum",
        values_callable=_enum_values,
    )
    platform_enum = Enum(
        ContentPlatform,
        name="content_platform_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_kind: Mapped[ContentSourceKind] = mapped_column(source_kind_enum, nullable=False)
    platform: Mapped[ContentPlatform] = mapped_column(platform_enum, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    parser: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    target_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ContentSourceSnapshot(Base):
    __tablename__ = "content_source_snapshot"

    snapshot_format_enum = Enum(
        SnapshotFormat,
        name="snapshot_format_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_source_target.id"),
        nullable=True,
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snapshot_format: Mapped[SnapshotFormat] = mapped_column(snapshot_format_enum, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentBrainItem(Base):
    __tablename__ = "content_brain_item"

    platform_enum = Enum(
        ContentPlatform,
        name="content_platform_enum",
        values_callable=_enum_values,
        create_type=False,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_source_target.id"),
        nullable=True,
    )
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_source_snapshot.id"),
        nullable=True,
    )
    canonical_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    platform: Mapped[ContentPlatform] = mapped_column(platform_enum, nullable=False)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ContentBrainAsset(Base):
    __tablename__ = "content_brain_asset"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_brain_item.id"),
        nullable=False,
    )
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    asset_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentBrainMetricSnapshot(Base):
    __tablename__ = "content_brain_metric_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_brain_item.id"),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
