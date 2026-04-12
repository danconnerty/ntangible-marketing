"""add phase 11 content expansion tables

Revision ID: 20260407_add_phase11_content_expansion_tables
Revises: 20260407_add_revenue_engine_tables
Create Date: 2026-04-07 23:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260407_add_phase11_content_expansion_tables"
down_revision: Union[str, Sequence[str], None] = "20260407_add_revenue_engine_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    platform_enum = postgresql.ENUM(
        "x",
        "linkedin",
        "instagram",
        "newsletter",
        name="platform_enum",
        create_type=False,
    )

    op.create_table(
        "science_content_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "science_type",
            sa.Enum(
                "advisor_spotlight",
                "white_paper_excerpt",
                "peer_review_milestone",
                name="science_content_type_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "review_ready",
                "published",
                "failed",
                name="science_content_status_enum",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="linkedin"),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_slug", sa.String(length=255), nullable=True),
        sa.Column("trigger_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("draft_variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_focus", sa.Text(), nullable=True),
        sa.Column("source_notes", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["trigger_events.id"]),
        sa.ForeignKeyConstraint(["content_job_id"], ["content_jobs.id"]),
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "blog_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("meta_description", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(length=255), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("angle", sa.Text(), nullable=True),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("target_keywords", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("headings", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum("draft", "review_ready", "published", "failed", name="blog_article_status_enum"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("cms_provider", sa.String(length=64), nullable=True),
        sa.Column("cms_article_id", sa.String(length=128), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("publish_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "video_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "founder_raw",
                "reel_from_static",
                "testimonial",
                "partner_cutdown",
                name="video_brief_kind_enum",
            ),
            nullable=False,
        ),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("brief_format", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "ready", "needs_review", "briefed", "archived", name="video_brief_status_enum"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("hook", sa.Text(), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("script", sa.Text(), nullable=False),
        sa.Column("shot_list", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("motion_graphic_notes", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("cta", sa.Text(), nullable=True),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("source_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trigger_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("draft_variant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["trigger_events.id"]),
        sa.ForeignKeyConstraint(["content_job_id"], ["content_jobs.id"]),
        sa.ForeignKeyConstraint(["draft_variant_id"], ["draft_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ugc_testimonial_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_name", sa.String(length=255), nullable=False),
        sa.Column("athlete_email", sa.String(length=255), nullable=True),
        sa.Column("parent_name", sa.String(length=255), nullable=True),
        sa.Column("parent_email", sa.String(length=255), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("score_tier", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("preview_text", sa.Text(), nullable=False),
        sa.Column("request_copy", sa.Text(), nullable=False),
        sa.Column("graphic_path", sa.Text(), nullable=True),
        sa.Column("graphic_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "sent", "acknowledged", "archived", name="ugc_request_status_enum"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("source_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trigger_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("video_brief_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["trigger_events.id"]),
        sa.ForeignKeyConstraint(["content_job_id"], ["content_jobs.id"]),
        sa.ForeignKeyConstraint(["video_brief_id"], ["video_briefs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ugc_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("testimonial_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("athlete_name", sa.String(length=255), nullable=False),
        sa.Column("athlete_email", sa.String(length=255), nullable=True),
        sa.Column("parent_name", sa.String(length=255), nullable=True),
        sa.Column("parent_email", sa.String(length=255), nullable=True),
        sa.Column("athlete_age", sa.Integer(), nullable=True),
        sa.Column("consent_athlete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consent_parent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consent_share", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("score_tier", sa.String(length=64), nullable=False),
        sa.Column("video_url", sa.Text(), nullable=False),
        sa.Column("testimonial_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("received", "accepted", "needs_review", "rejected", name="ugc_submission_status_enum"),
            nullable=False,
            server_default="received",
        ),
        sa.Column("shareable_score_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("graphic_path", sa.Text(), nullable=True),
        sa.Column("graphic_url", sa.Text(), nullable=True),
        sa.Column("source_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trigger_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("video_brief_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["testimonial_request_id"], ["ugc_testimonial_requests.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["trigger_events.id"]),
        sa.ForeignKeyConstraint(["content_job_id"], ["content_jobs.id"]),
        sa.ForeignKeyConstraint(["video_brief_id"], ["video_briefs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sports_calendar_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sport", sa.String(length=64), nullable=False),
        sa.Column("window_type", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("content_bucket", sa.String(length=64), nullable=False),
        sa.Column("template_key", sa.String(length=64), nullable=False),
        sa.Column("default_platforms", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("stage_angle", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "sports_stage_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sports_calendar_window_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trigger_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("target_platforms", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["sports_calendar_window_id"], ["sports_calendar_windows.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["trigger_events.id"]),
        sa.ForeignKeyConstraint(["content_job_id"], ["content_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "repurposing_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "repurposing_derivatives",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repurposing_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trigger_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("derivative_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_platforms", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_blog_draft", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repurposing_source_id"], ["repurposing_sources.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        sa.ForeignKeyConstraint(["trigger_event_id"], ["trigger_events.id"]),
        sa.ForeignKeyConstraint(["content_job_id"], ["content_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "repurposing_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repurposing_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("derivative_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repurposing_source_id"], ["repurposing_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("repurposing_runs")
    op.drop_table("repurposing_derivatives")
    op.drop_table("repurposing_sources")
    op.drop_table("sports_stage_runs")
    op.drop_table("sports_calendar_windows")
    op.drop_table("ugc_submissions")
    op.drop_table("ugc_testimonial_requests")
    op.drop_table("video_briefs")
    op.drop_table("blog_articles")
    op.drop_table("science_content_records")
