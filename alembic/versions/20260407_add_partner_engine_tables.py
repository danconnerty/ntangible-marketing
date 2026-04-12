"""add partner engine tables

Revision ID: 20260407_add_partner_engine_tables
Revises: 20260407_add_phase11_lead_tables
Create Date: 2026-04-07 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260407_add_partner_engine_tables"
down_revision: Union[str, Sequence[str], None] = "20260407_add_phase11_lead_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "partner_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("portal_username", sa.String(length=128), nullable=False),
        sa.Column("portal_password_hash", sa.String(length=255), nullable=False),
        sa.Column("webhook_secret", sa.String(length=255), nullable=False),
        sa.Column("supported_event_types", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("routing_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("delivery_defaults", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portal_username"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "partner_event_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("intake_source", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("normalized_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("trigger_event_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["partner_account_id"], ["partner_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("partner_account_id", "event_type", "external_event_id"),
    )
    op.create_table(
        "partner_delivery_bundles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_event_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("hashtags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("asset_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("delivery_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("usage_notes", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
        sa.ForeignKeyConstraint(["partner_account_id"], ["partner_accounts.id"]),
        sa.ForeignKeyConstraint(["partner_event_record_id"], ["partner_event_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("draft_variants", sa.Column("intent", sa.String(length=32), nullable=False, server_default="brand"))
    op.add_column("draft_variants", sa.Column("partner_slug", sa.String(length=128), nullable=True))
    op.add_column("draft_variants", sa.Column("partner_name", sa.String(length=255), nullable=True))
    op.add_column("draft_variants", sa.Column("source_event_type", sa.String(length=64), nullable=True))
    op.add_column("draft_variants", sa.Column("source_event_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("draft_variants", "source_event_id")
    op.drop_column("draft_variants", "source_event_type")
    op.drop_column("draft_variants", "partner_name")
    op.drop_column("draft_variants", "partner_slug")
    op.drop_column("draft_variants", "intent")
    op.drop_table("partner_delivery_bundles")
    op.drop_table("partner_event_records")
    op.drop_table("partner_accounts")
