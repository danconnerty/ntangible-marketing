"""add ingestion queue table and extend connection channel enum

Revision ID: 20260411_add_ingestion_queue
Revises: 98fbddb3c753
Create Date: 2026-04-11 22:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260411_add_ingestion_queue"
down_revision: Union[str, Sequence[str], None] = "98fbddb3c753"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE connection_channel_enum ADD VALUE IF NOT EXISTS 'gmail'")
    op.execute("ALTER TYPE connection_channel_enum ADD VALUE IF NOT EXISTS 'calendar'")
    op.execute("ALTER TYPE connection_channel_enum ADD VALUE IF NOT EXISTS 'telegram'")

    op.create_table(
        "ingestion_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=512), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(length=128), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "classification",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_ingestion_source"),
    )
    op.create_index(
        "ix_ingestion_queue_status_created",
        "ingestion_queue",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_queue_status_created", table_name="ingestion_queue")
    op.drop_table("ingestion_queue")
