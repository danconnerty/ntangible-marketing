"""add content brain storage tables

Revision ID: 20260407_add_content_brain_tables
Revises: 20260406_add_linkedin_tables
Create Date: 2026-04-07 00:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260407_add_content_brain_tables"
down_revision: Union[str, Sequence[str], None] = "20260406_add_linkedin_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


content_source_kind_enum = postgresql.ENUM(
    "website",
    "partner_page",
    "wayback",
    "feed",
    "social",
    "external",
    name="content_source_kind_enum",
)
content_platform_enum = postgresql.ENUM(
    "web",
    "youtube",
    "instagram",
    "linkedin",
    "other",
    name="content_platform_enum",
)
snapshot_format_enum = postgresql.ENUM(
    "html",
    "xml",
    "json",
    "text",
    name="snapshot_format_enum",
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    content_source_kind_enum.create(bind, checkfirst=True)
    content_platform_enum.create(bind, checkfirst=True)
    snapshot_format_enum.create(bind, checkfirst=True)

    op.create_table(
        "content_source_target",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "source_kind",
            postgresql.ENUM(
                "website",
                "partner_page",
                "wayback",
                "feed",
                "social",
                "external",
                name="content_source_kind_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "platform",
            postgresql.ENUM(
                "web",
                "youtube",
                "instagram",
                "linkedin",
                "other",
                name="content_platform_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("parser", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("target_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "content_source_snapshot",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column(
            "snapshot_format",
            postgresql.ENUM(
                "html",
                "xml",
                "json",
                "text",
                name="snapshot_format_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("body_sha256", sa.String(length=64), nullable=True),
        sa.Column("snapshot_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["target_id"], ["content_source_target.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "content_brain_item",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column("snapshot_id", sa.UUID(), nullable=True),
        sa.Column("canonical_key", sa.String(length=512), nullable=False),
        sa.Column(
            "platform",
            postgresql.ENUM(
                "web",
                "youtube",
                "instagram",
                "linkedin",
                "other",
                name="content_platform_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("item_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(["snapshot_id"], ["content_source_snapshot.id"]),
        sa.ForeignKeyConstraint(["target_id"], ["content_source_target.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_key"),
    )

    op.create_table(
        "content_brain_asset",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=False),
        sa.Column("asset_type", sa.String(length=64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("asset_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_brain_item.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "content_brain_metric_snapshot",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("metric_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_brain_item.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("content_brain_metric_snapshot")
    op.drop_table("content_brain_asset")
    op.drop_table("content_brain_item")
    op.drop_table("content_source_snapshot")
    op.drop_table("content_source_target")

    bind = op.get_bind()
    snapshot_format_enum.drop(bind, checkfirst=True)
    content_platform_enum.drop(bind, checkfirst=True)
    content_source_kind_enum.drop(bind, checkfirst=True)
