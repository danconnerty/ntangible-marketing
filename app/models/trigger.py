import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class TriggerType(str, enum.Enum):
    CALENDAR = "calendar"
    EXTERNAL = "external"
    MANUAL_REQUEST = "manual_request"


class PartnerSourceType(str, enum.Enum):
    WEBHOOK = "webhook"
    PORTAL = "portal"
    SPREADSHEET = "spreadsheet"


class TriggerProcessingStatus(str, enum.Enum):
    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"


class PartnerSource(Base):
    __tablename__ = "partner_sources"

    partner_source_type_enum = Enum(
        PartnerSourceType,
        name="partner_source_type_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[PartnerSourceType] = mapped_column(partner_source_type_enum, nullable=False)
    webhook_secret: Mapped[str | None] = mapped_column(String(256), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class CalendarRule(Base):
    __tablename__ = "calendar_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/New_York")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    publish_hour_local: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publish_minute_local: Mapped[int | None] = mapped_column(Integer, nullable=True)
    all_day_generation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    next_fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class TriggerEvent(Base):
    __tablename__ = "trigger_events"

    trigger_type_enum = Enum(
        TriggerType,
        name="trigger_type_enum",
        values_callable=_enum_values,
    )
    trigger_processing_status_enum = Enum(
        TriggerProcessingStatus,
        name="trigger_processing_status_enum",
        values_callable=_enum_values,
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trigger_type: Mapped[TriggerType] = mapped_column(trigger_type_enum, nullable=False)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    calendar_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendar_rules.id"), nullable=True
    )
    # Partner/external event fields
    partner_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partner_sources.id"), nullable=True
    )
    external_event_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_event_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    processing_status: Mapped[TriggerProcessingStatus] = mapped_column(
        trigger_processing_status_enum,
        nullable=False,
        default=TriggerProcessingStatus.RECEIVED,
    )
    dedupe_key: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
