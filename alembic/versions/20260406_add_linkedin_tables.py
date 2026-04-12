"""add linkedin_post and linkedin_generation_log tables

Revision ID: 20260406_add_linkedin_tables
Revises: 3f2398b53f3d
Create Date: 2026-04-06 23:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260406_add_linkedin_tables"
down_revision: Union[str, Sequence[str], None] = "3f2398b53f3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


linkedin_content_type_enum = postgresql.ENUM(
    "thought_leadership",
    "data_insight",
    "company_update",
    name="linkedin_content_type_enum",
)
linkedin_approval_tier_enum = postgresql.ENUM(
    "tier_1",
    "tier_2",
    "tier_3",
    name="linkedin_approval_tier_enum",
)
linkedin_status_enum = postgresql.ENUM(
    "draft",
    "needs_review",
    "approved",
    "publishing",
    "published",
    "publishing_unknown",
    "failed",
    "rejected",
    name="linkedin_status_enum",
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    linkedin_content_type_enum.create(bind, checkfirst=True)
    linkedin_approval_tier_enum.create(bind, checkfirst=True)
    linkedin_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "linkedin_post",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "content_type",
            postgresql.ENUM(
                "thought_leadership",
                "data_insight",
                "company_update",
                name="linkedin_content_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "pillar",
            postgresql.ENUM(
                "blind_spot",
                "cost_of_guessing",
                "client_proof",
                "thought_leadership",
                "product",
                name="pillar_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "intent",
            postgresql.ENUM(
                "brand",
                "partner",
                "revenue",
                name="intent_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("hashtags", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column(
            "approval_tier",
            postgresql.ENUM(
                "tier_1",
                "tier_2",
                "tier_3",
                name="linkedin_approval_tier_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "needs_review",
                "approved",
                "publishing",
                "published",
                "publishing_unknown",
                "failed",
                "rejected",
                name="linkedin_status_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("compliance_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        # External LinkedIn platform post id (string), returned after publish.
        sa.Column("linkedin_post_id", sa.String(length=128), nullable=True),
        sa.Column("post_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "linkedin_generation_log",
        sa.Column("id", sa.UUID(), nullable=False),
        # Internal reference to linkedin_post.id (UUID), not the external LinkedIn id.
        sa.Column("linkedin_post_id", sa.UUID(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("linkedin_generation_log")
    op.drop_table("linkedin_post")

    bind = op.get_bind()
    linkedin_status_enum.drop(bind, checkfirst=True)
    linkedin_approval_tier_enum.drop(bind, checkfirst=True)
    linkedin_content_type_enum.drop(bind, checkfirst=True)
