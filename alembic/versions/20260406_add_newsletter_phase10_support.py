"""add newsletter phase 10 platform enum support

Revision ID: 20260406_add_newsletter_phase10_support
Revises: 20260406_add_phase11_campaign_tables
Create Date: 2026-04-06 23:59:30.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260406_add_newsletter_phase10_support"
down_revision: Union[str, Sequence[str], None] = "20260406_add_phase11_campaign_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE platform_enum ADD VALUE IF NOT EXISTS 'newsletter'")


def downgrade() -> None:
    # PostgreSQL enum value removal is intentionally omitted to avoid destructive downgrade behavior.
    pass
