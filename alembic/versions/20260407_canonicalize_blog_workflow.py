"""canonicalize blog workflow integration

Revision ID: 20260407_canonicalize_blog_workflow
Revises: 20260407_add_phase11_content_expansion_tables
Create Date: 2026-04-07 23:59:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260407_canonicalize_blog_workflow"
down_revision: Union[str, Sequence[str], None] = "20260407_add_phase11_content_expansion_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE platform_enum ADD VALUE IF NOT EXISTS 'blog'")

    op.add_column("blog_articles", sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("blog_articles", sa.Column("trigger_event_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("blog_articles", sa.Column("content_job_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("blog_articles", sa.Column("draft_variant_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.create_foreign_key(
        "fk_blog_articles_workflow_id_workflows",
        "blog_articles",
        "workflows",
        ["workflow_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_blog_articles_trigger_event_id_trigger_events",
        "blog_articles",
        "trigger_events",
        ["trigger_event_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_blog_articles_content_job_id_content_jobs",
        "blog_articles",
        "content_jobs",
        ["content_job_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_blog_articles_draft_variant_id_draft_variants",
        "blog_articles",
        "draft_variants",
        ["draft_variant_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_blog_articles_draft_variant_id_draft_variants", "blog_articles", type_="foreignkey")
    op.drop_constraint("fk_blog_articles_content_job_id_content_jobs", "blog_articles", type_="foreignkey")
    op.drop_constraint("fk_blog_articles_trigger_event_id_trigger_events", "blog_articles", type_="foreignkey")
    op.drop_constraint("fk_blog_articles_workflow_id_workflows", "blog_articles", type_="foreignkey")

    op.drop_column("blog_articles", "draft_variant_id")
    op.drop_column("blog_articles", "content_job_id")
    op.drop_column("blog_articles", "trigger_event_id")
    op.drop_column("blog_articles", "workflow_id")

    # PostgreSQL enum value removal is intentionally omitted here.
