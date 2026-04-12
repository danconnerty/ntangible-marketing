"""add phase 6 analytics tables

Revision ID: 20260406_add_phase6_analytics_tables
Revises: 20260406_add_instagram_phase4_tables
Create Date: 2026-04-06 19:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260406_add_phase6_analytics_tables"
down_revision: Union[str, Sequence[str], None] = (
    "20260406_add_instagram_phase4_tables",
    "20260406_add_memory_and_analytics_tables",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "publication_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("draft_variant_id", sa.UUID(), nullable=False),
        sa.Column("content_job_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("workflow_version_id", sa.UUID(), nullable=False),
        sa.Column("trigger_event_id", sa.UUID(), nullable=True),
        sa.Column(
            "platform",
            postgresql.ENUM("x", "linkedin", "instagram", name="platform_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("platform_post_id", sa.String(length=128), nullable=True),
        sa.Column("post_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publish_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
        sa.ForeignKeyConstraint(["content_job_id"], ["content_jobs.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["workflow_version_id"], ["workflow_versions.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["trigger_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "analytics_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("publication_record_id", sa.UUID(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["publication_record_id"], ["publication_records.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "workflow_metrics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("workflow_version_id", sa.UUID(), nullable=True),
        sa.Column(
            "platform",
            postgresql.ENUM("x", "linkedin", "instagram", name="platform_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("trigger_type", sa.String(length=64), nullable=True),
        sa.Column("window_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("approval_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rejection_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("expiration_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("publication_success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("engagement_percentile", sa.Float(), nullable=False, server_default="0"),
        sa.Column("promotion_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["workflow_version_id"], ["workflow_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("workflow_metrics")
    op.drop_table("analytics_snapshots")
    op.drop_table("publication_records")
