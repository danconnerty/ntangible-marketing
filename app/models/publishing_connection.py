import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.workflow import _enum_values


class ConnectionChannel(str, enum.Enum):
    X = "x"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    NEWSLETTER = "newsletter"
    BLOG = "blog"
    GMAIL = "gmail"
    CALENDAR = "calendar"
    TELEGRAM = "telegram"


class ConnectionStatus(str, enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ACTION_REQUIRED = "action_required"
    FAILED = "failed"


class AppConnection(Base):
    __tablename__ = "app_connections"

    channel_enum = Enum(
        ConnectionChannel,
        name="connection_channel_enum",
        values_callable=_enum_values,
    )
    status_enum = Enum(
        ConnectionStatus,
        name="connection_status_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel: Mapped[ConnectionChannel] = mapped_column(channel_enum, nullable=False, unique=True)
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    auth_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[ConnectionStatus] = mapped_column(status_enum, nullable=False, default=ConnectionStatus.DISCONNECTED)
    connection_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    credential_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    destinations: Mapped[list["PublishingDestination"]] = relationship(
        back_populates="app_connection",
        cascade="all, delete-orphan",
    )


class PublishingDestination(Base):
    __tablename__ = "publishing_destinations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_connections.id"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_type: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    app_connection: Mapped[AppConnection] = relationship(back_populates="destinations")
