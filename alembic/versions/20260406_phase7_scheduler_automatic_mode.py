"""add phase 7 scheduler and automatic mode fields

Revision ID: 20260406_phase7_scheduler_automatic_mode
Revises: 20260406_add_memory_and_analytics_tables, 20260406_add_phase6_analytics_tables
Create Date: 2026-04-06 23:59:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260406_phase7_scheduler_automatic_mode"
down_revision: Union[str, Sequence[str], None] = (
    "20260406_add_memory_and_analytics_tables",
    "20260406_add_phase6_analytics_tables",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="America/New_York"),
    )
    op.add_column("workflows", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflows", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflows", sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workflows", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column(
        "workflows",
        sa.Column("health_status", sa.String(length=32), nullable=False, server_default="healthy"),
    )

    op.add_column("calendar_rules", sa.Column("publish_hour_local", sa.Integer(), nullable=True))
    op.add_column("calendar_rules", sa.Column("publish_minute_local", sa.Integer(), nullable=True))
    op.add_column(
        "calendar_rules",
        sa.Column("all_day_generation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("calendar_rules", sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("calendar_rules", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("calendar_rules", sa.Column("claimed_by", sa.String(length=128), nullable=True))

    op.add_column("draft_variants", sa.Column("publish_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("draft_variants", sa.Column("published_via", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("draft_variants", "published_via")
    op.drop_column("draft_variants", "publish_attempted_at")

    op.drop_column("calendar_rules", "claimed_by")
    op.drop_column("calendar_rules", "claimed_at")
    op.drop_column("calendar_rules", "last_fired_at")
    op.drop_column("calendar_rules", "all_day_generation")
    op.drop_column("calendar_rules", "publish_minute_local")
    op.drop_column("calendar_rules", "publish_hour_local")

    op.drop_column("workflows", "health_status")
    op.drop_column("workflows", "last_error")
    op.drop_column("workflows", "last_success_at")
    op.drop_column("workflows", "last_run_at")
    op.drop_column("workflows", "paused_at")
    op.drop_column("workflows", "timezone")
