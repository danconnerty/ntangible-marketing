"""add publishing connection tables

Revision ID: 20260409_add_publishing_connection_tables
Revises: 20260407_canonicalize_blog_workflow
Create Date: 2026-04-09 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260409_add_publishing_connection_tables"
down_revision: Union[str, Sequence[str], None] = "20260407_canonicalize_blog_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


connection_channel_enum = postgresql.ENUM(
    "x",
    "linkedin",
    "instagram",
    "newsletter",
    "blog",
    name="connection_channel_enum",
)
connection_status_enum = postgresql.ENUM(
    "disconnected",
    "connected",
    "action_required",
    "failed",
    name="connection_status_enum",
)


def upgrade() -> None:
    bind = op.get_bind()
    connection_channel_enum.create(bind, checkfirst=True)
    connection_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "app_connections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "channel",
            postgresql.ENUM(
                "x",
                "linkedin",
                "instagram",
                "newsletter",
                "blog",
                name="connection_channel_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("auth_mode", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "disconnected",
                "connected",
                "action_required",
                "failed",
                name="connection_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="disconnected",
        ),
        sa.Column("connection_label", sa.String(length=255), nullable=True),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "credential_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("channel"),
    )

    op.create_table(
        "publishing_destinations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("app_connection_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("destination_type", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.ForeignKeyConstraint(["app_connection_id"], ["app_connections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("publishing_destinations")
    op.drop_table("app_connections")

    bind = op.get_bind()
    connection_status_enum.drop(bind, checkfirst=True)
    connection_channel_enum.drop(bind, checkfirst=True)
