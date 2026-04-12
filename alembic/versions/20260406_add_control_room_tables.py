"""add control room tables: workflows, versions, triggers, jobs, drafts, reviews, assets

Revision ID: 20260406_add_control_room_tables
Revises: 20260407_add_content_brain_tables
Create Date: 2026-04-06 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260406_add_control_room_tables"
down_revision: Union[str, Sequence[str], None] = "20260407_add_content_brain_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


workflow_mode_enum = postgresql.ENUM("manual", "automatic", name="workflow_mode_enum")
platform_enum = postgresql.ENUM("x", "linkedin", "instagram", name="platform_enum")
draft_state_enum = postgresql.ENUM(
    "generated", "manual_ready", "scheduled_manual", "automatic_ready",
    "publishing", "published", "failed", "rejected", "expired",
    name="draft_state_enum",
)
trigger_type_enum = postgresql.ENUM("calendar", "external", "manual_request", name="trigger_type_enum")
review_action_type_enum = postgresql.ENUM(
    "post_now", "schedule", "reject", "expire", "pause", "move_to_manual",
    name="review_action_type_enum",
)
partner_source_type_enum = postgresql.ENUM("webhook", "portal", "spreadsheet", name="partner_source_type_enum")
trigger_processing_status_enum = postgresql.ENUM("received", "processed", "failed", name="trigger_processing_status_enum")


def upgrade() -> None:
    """Create control room tables."""
    bind = op.get_bind()
    workflow_mode_enum.create(bind, checkfirst=True)
    platform_enum.create(bind, checkfirst=True)
    draft_state_enum.create(bind, checkfirst=True)
    trigger_type_enum.create(bind, checkfirst=True)
    review_action_type_enum.create(bind, checkfirst=True)
    partner_source_type_enum.create(bind, checkfirst=True)
    trigger_processing_status_enum.create(bind, checkfirst=True)

    # --- partner_sources ---
    op.create_table(
        "partner_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column(
            "source_type",
            postgresql.ENUM("webhook", "portal", "spreadsheet", name="partner_source_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("webhook_secret", sa.String(length=256), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # --- workflows ---
    op.create_table(
        "workflows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "mode",
            postgresql.ENUM("manual", "automatic", name="workflow_mode_enum", create_type=False),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "platform",
            postgresql.ENUM("x", "linkedin", "instagram", name="platform_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("active_version_id", sa.UUID(), nullable=True),
        sa.Column("fallback_version_id", sa.UUID(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # --- workflow_versions ---
    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version_note", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.UniqueConstraint("workflow_id", "version_number"),
    )

    # Add FK from workflows.active_version_id now that workflow_versions exists
    op.create_foreign_key(
        "fk_workflows_active_version",
        "workflows", "workflow_versions",
        ["active_version_id"], ["id"],
    )

    # --- calendar_rules ---
    op.create_table(
        "calendar_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("cron_expression", sa.String(length=128), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="America/New_York"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("next_fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
    )

    # --- trigger_events ---
    op.create_table(
        "trigger_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "trigger_type",
            postgresql.ENUM("calendar", "external", "manual_request", name="trigger_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("calendar_rule_id", sa.UUID(), nullable=True),
        sa.Column("partner_source_id", sa.UUID(), nullable=True),
        sa.Column("external_event_type", sa.String(length=128), nullable=True),
        sa.Column("external_event_id", sa.String(length=256), nullable=True),
        sa.Column(
            "processing_status",
            postgresql.ENUM("received", "processed", "failed", name="trigger_processing_status_enum", create_type=False),
            nullable=False,
            server_default="received",
        ),
        sa.Column("dedupe_key", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("source_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["calendar_rule_id"], ["calendar_rules.id"]),
        sa.ForeignKeyConstraint(["partner_source_id"], ["partner_sources.id"]),
        sa.UniqueConstraint("dedupe_key"),
    )

    # --- content_jobs ---
    op.create_table(
        "content_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("workflow_version_id", sa.UUID(), nullable=False),
        sa.Column("trigger_event_id", sa.UUID(), nullable=False),
        sa.Column("prompt_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("retrieved_memory_ids", postgresql.ARRAY(sa.UUID()), nullable=True),
        sa.Column("compliance_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["workflow_version_id"], ["workflow_versions.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["trigger_events.id"]),
    )

    # --- draft_variants ---
    op.create_table(
        "draft_variants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("content_job_id", sa.UUID(), nullable=False),
        sa.Column(
            "platform",
            postgresql.ENUM("x", "linkedin", "instagram", name="platform_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("hashtags", postgresql.ARRAY(sa.String()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column(
            "state",
            postgresql.ENUM(
                "generated", "manual_ready", "scheduled_manual", "automatic_ready",
                "publishing", "published", "failed", "rejected", "expired",
                name="draft_state_enum", create_type=False,
            ),
            nullable=False,
            server_default="generated",
        ),
        sa.Column("recommended_publish_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_publish_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="America/New_York"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("compliance_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("platform_post_id", sa.String(length=128), nullable=True),
        sa.Column("post_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["content_job_id"], ["content_jobs.id"]),
    )

    # --- review_actions ---
    op.create_table(
        "review_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("draft_variant_id", sa.UUID(), nullable=False),
        sa.Column(
            "action",
            postgresql.ENUM(
                "post_now", "schedule", "reject", "expire", "pause", "move_to_manual",
                name="review_action_type_enum", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
    )

    # --- assets ---
    op.create_table(
        "assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("draft_variant_id", sa.UUID(), nullable=True),
        sa.Column("workflow_id", sa.UUID(), nullable=True),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=256), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("platform_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
    )


def downgrade() -> None:
    """Drop control room tables."""
    op.drop_table("assets")
    op.drop_table("review_actions")
    op.drop_table("draft_variants")
    op.drop_table("content_jobs")
    op.drop_table("trigger_events")
    op.drop_table("calendar_rules")
    op.drop_constraint("fk_workflows_active_version", "workflows", type_="foreignkey")
    op.drop_table("workflow_versions")
    op.drop_table("workflows")
    op.drop_table("partner_sources")

    bind = op.get_bind()
    review_action_type_enum.drop(bind, checkfirst=True)
    trigger_processing_status_enum.drop(bind, checkfirst=True)
    partner_source_type_enum.drop(bind, checkfirst=True)
    trigger_type_enum.drop(bind, checkfirst=True)
    draft_state_enum.drop(bind, checkfirst=True)
    platform_enum.drop(bind, checkfirst=True)
    workflow_mode_enum.drop(bind, checkfirst=True)
