"""add memory and analytics tables for control room

Revision ID: 20260406_add_memory_and_analytics_tables
Revises: 20260406_add_control_room_tables
Create Date: 2026-04-06 18:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260406_add_memory_and_analytics_tables"
down_revision: Union[str, Sequence[str], None] = "20260406_add_control_room_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


memory_bucket_enum = postgresql.ENUM(
    "approved",
    "rejected",
    "expired",
    "failed",
    "draft",
    "source",
    name="memory_bucket_enum",
)
memory_source_kind_enum = postgresql.ENUM(
    "draft_variant",
    "legacy_x",
    "legacy_linkedin",
    "legacy_instagram",
    "content_brain",
    "trigger_event",
    name="memory_source_kind_enum",
)


def upgrade() -> None:
    bind = op.get_bind()
    memory_bucket_enum.create(bind, checkfirst=True)
    memory_source_kind_enum.create(bind, checkfirst=True)

    op.execute("ALTER TYPE draft_state_enum ADD VALUE IF NOT EXISTS 'render_failed'")
    op.execute("ALTER TYPE draft_state_enum ADD VALUE IF NOT EXISTS 'needs_design_review'")

    op.create_table(
        "memory_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "source_kind",
            postgresql.ENUM(
                "draft_variant",
                "legacy_x",
                "legacy_linkedin",
                "legacy_instagram",
                "content_brain",
                "trigger_event",
                name="memory_source_kind_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column(
            "bucket",
            postgresql.ENUM(
                "approved",
                "rejected",
                "expired",
                "failed",
                "draft",
                "source",
                name="memory_bucket_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "platform",
            postgresql.ENUM("x", "linkedin", "instagram", name="platform_enum", create_type=False),
            nullable=True,
        ),
        sa.Column("workflow_id", sa.UUID(), nullable=True),
        sa.Column("workflow_slug", sa.String(length=255), nullable=True),
        sa.Column("draft_variant_id", sa.UUID(), nullable=True),
        sa.Column("trigger_event_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["trigger_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_kind", "source_id", name="uq_memory_item_source"),
    )

    op.create_table(
        "memory_embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("memory_item_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="metadata_only"),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("dimensions", sa.Integer(), nullable=True),
        sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["memory_item_id"], ["memory_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "draft_analytics_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("draft_variant_id", sa.UUID(), nullable=False),
        sa.Column(
            "platform",
            postgresql.ENUM("x", "linkedin", "instagram", name="platform_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "workflow_analytics_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column(
            "platform",
            postgresql.ENUM("x", "linkedin", "instagram", name="platform_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("workflow_name", sa.String(length=255), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_generated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_published", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_expired", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approval_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("publish_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("workflow_analytics_snapshots")
    op.drop_table("draft_analytics_snapshots")
    op.drop_table("memory_embeddings")
    op.drop_table("memory_items")

    bind = op.get_bind()
    memory_source_kind_enum.drop(bind, checkfirst=True)
    memory_bucket_enum.drop(bind, checkfirst=True)
