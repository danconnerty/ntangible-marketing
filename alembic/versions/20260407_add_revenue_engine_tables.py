"""add revenue engine tables

Revision ID: 20260407_add_revenue_engine_tables
Revises: 20260407_add_partner_engine_tables
Create Date: 2026-04-07 23:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260407_add_revenue_engine_tables"
down_revision: Union[str, Sequence[str], None] = "20260407_add_partner_engine_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "revenue_playbooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("playbook_type", sa.String(length=64), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_output", sa.String(length=64), nullable=True),
        sa.Column("persona", sa.String(length=128), nullable=False),
        sa.Column("offer", sa.Text(), nullable=False),
        sa.Column("cta", sa.Text(), nullable=False),
        sa.Column("default_audience", sa.Text(), nullable=True),
        sa.Column("default_proof_points", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "revenue_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revenue_playbook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("trigger_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["revenue_playbook_id"], ["revenue_playbooks.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["trigger_events.id"]),
        sa.ForeignKeyConstraint(["content_job_id"], ["content_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "conversion_goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("metric_type", sa.String(length=64), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revenue_playbook_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_count", sa.Integer(), nullable=True),
        sa.Column("target_rate", sa.Float(), nullable=True),
        sa.Column("attribution_window_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["revenue_playbook_id"], ["revenue_playbooks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "conversion_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversion_goal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=False),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("partner_slug", sa.String(length=128), nullable=True),
        sa.Column("lead_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversion_goal_id"], ["conversion_goals.id"]),
        sa.ForeignKeyConstraint(["lead_account_id"], ["lead_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversion_goal_id", "external_event_id"),
    )
    op.create_table(
        "sales_enablement_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("partner_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("partner_event_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revenue_playbook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("package_kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("body_copy", sa.Text(), nullable=False),
        sa.Column("cta", sa.Text(), nullable=False),
        sa.Column("asset_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("usage_notes", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["partner_account_id"], ["partner_accounts.id"]),
        sa.ForeignKeyConstraint(["partner_event_record_id"], ["partner_event_records.id"]),
        sa.ForeignKeyConstraint(["revenue_playbook_id"], ["revenue_playbooks.id"]),
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sales_enablement_packages")
    op.drop_table("conversion_events")
    op.drop_table("conversion_goals")
    op.drop_table("revenue_executions")
    op.drop_table("revenue_playbooks")
