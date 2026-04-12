"""add instagram phase 4 tables

Revision ID: 20260406_add_instagram_phase4_tables
Revises: 20260406_add_control_room_tables
Create Date: 2026-04-06 18:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260406_add_instagram_phase4_tables"
down_revision: Union[str, Sequence[str], None] = "20260406_add_control_room_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


instagram_content_type_enum = postgresql.ENUM(
    "athlete_spotlight",
    "education_carousel",
    "reel",
    "partner_content",
    "story",
    "stat_card",
    name="instagram_content_type_enum",
)
instagram_template_family_enum = postgresql.ENUM(
    "athlete_spotlight",
    "commitment_post",
    "clutch_certified",
    "event_leaderboard",
    "bold_statement",
    "education_carousel",
    "story_poll",
    "story_repost",
    "partner_event_spotlight",
    name="instagram_template_family_enum",
)
instagram_render_status_enum = postgresql.ENUM(
    "pending",
    "rendering",
    "succeeded",
    "failed",
    "needs_design_review",
    name="instagram_render_status_enum",
)
partner_package_status_enum = postgresql.ENUM(
    "needs_review",
    "approved",
    "delivered",
    "rejected",
    "failed",
    name="partner_package_status_enum",
)
partner_delivery_channel_enum = postgresql.ENUM(
    "dashboard",
    "email",
    "export",
    name="partner_delivery_channel_enum",
)


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("ALTER TYPE draft_state_enum ADD VALUE IF NOT EXISTS 'render_failed'")
    op.execute("ALTER TYPE draft_state_enum ADD VALUE IF NOT EXISTS 'needs_design_review'")

    instagram_content_type_enum.create(bind, checkfirst=True)
    instagram_template_family_enum.create(bind, checkfirst=True)
    instagram_render_status_enum.create(bind, checkfirst=True)
    partner_package_status_enum.create(bind, checkfirst=True)
    partner_delivery_channel_enum.create(bind, checkfirst=True)

    op.add_column("assets", sa.Column("asset_role", sa.String(length=64), nullable=True))
    op.add_column("assets", sa.Column("provider", sa.String(length=64), nullable=True))
    op.add_column("assets", sa.Column("render_status", sa.String(length=32), nullable=True))
    op.add_column(
        "assets",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "instagram_generation_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("draft_variant_id", sa.UUID(), nullable=False),
        sa.Column("prompt_snapshot", sa.Text(), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_estimate", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "instagram_render_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("draft_variant_id", sa.UUID(), nullable=False),
        sa.Column(
            "template_family",
            postgresql.ENUM(
                "athlete_spotlight",
                "commitment_post",
                "clutch_certified",
                "event_leaderboard",
                "bold_statement",
                "education_carousel",
                "story_poll",
                "story_repost",
                "partner_event_spotlight",
                name="instagram_template_family_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "rendering",
                "succeeded",
                "failed",
                "needs_design_review",
                name="instagram_render_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("provider_job_id", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "partner_delivery_packages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("draft_variant_id", sa.UUID(), nullable=False),
        sa.Column("partner_name", sa.String(length=128), nullable=False),
        sa.Column("source_event_type", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "needs_review",
                "approved",
                "delivered",
                "rejected",
                "failed",
                name="partner_package_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="needs_review",
        ),
        sa.Column(
            "delivery_channel",
            postgresql.ENUM(
                "dashboard",
                "email",
                "export",
                name="partner_delivery_channel_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("hashtags", postgresql.ARRAY(sa.String()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("asset_ids", postgresql.ARRAY(sa.UUID()), nullable=False, server_default=sa.text("'{}'::uuid[]")),
        sa.Column("delivery_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("partner_delivery_packages")
    op.drop_table("instagram_render_jobs")
    op.drop_table("instagram_generation_logs")

    op.drop_column("assets", "sort_order")
    op.drop_column("assets", "render_status")
    op.drop_column("assets", "provider")
    op.drop_column("assets", "asset_role")

    bind = op.get_bind()
    partner_delivery_channel_enum.drop(bind, checkfirst=True)
    partner_package_status_enum.drop(bind, checkfirst=True)
    instagram_render_status_enum.drop(bind, checkfirst=True)
    instagram_template_family_enum.drop(bind, checkfirst=True)
    instagram_content_type_enum.drop(bind, checkfirst=True)
