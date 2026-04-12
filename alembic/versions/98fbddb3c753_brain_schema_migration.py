"""brain_schema_migration

Revision ID: 98fbddb3c753
Revises: 20260409_add_publishing_connection_tables
Create Date: 2026-04-09 17:59:29.133382

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '98fbddb3c753'
down_revision: Union[str, Sequence[str], None] = '20260409_add_publishing_connection_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. topic_profiles
    op.create_table(
        "topic_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("topic_key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="high"),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("context_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("intelligence_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_key"),
    )

    # 2. entity_nodes
    op.create_table(
        "entity_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("canonical_name", sa.String(length=256), nullable=False),
        sa.Column("slug", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("primary_topic_key", sa.String(length=64), nullable=True),
        sa.Column("search_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "slug", name="uq_entity_type_slug"),
    )
    op.create_index("ix_entity_type_status", "entity_nodes", ["entity_type", "status"])
    op.create_index("ix_entity_topic", "entity_nodes", ["primary_topic_key"])

    # 3. knowledge_nodes
    op.create_table(
        "knowledge_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("primary_topic_key", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("search_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_kind_status", "knowledge_nodes", ["kind", "status"])
    op.create_index("ix_knowledge_topic", "knowledge_nodes", ["primary_topic_key"])
    op.create_index("ix_knowledge_scheduler", "knowledge_nodes", ["status", "valid_from"])
    op.create_index("ix_knowledge_latest", "knowledge_nodes", ["kind", "status", "is_latest"])

    # 4. entity_edges
    op.create_table(
        "entity_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("relation", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entity_edge_source", "entity_edges", ["source_id"])
    op.create_index("ix_entity_edge_target", "entity_edges", ["target_id"])
    op.create_index("ix_entity_edge_source_rel", "entity_edges", ["source_id", "relation"])
    op.create_index("ix_entity_edge_target_rel", "entity_edges", ["target_id", "relation"])

    # 5. knowledge_edges
    op.create_table(
        "knowledge_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_nodes.id"]),
        sa.ForeignKeyConstraint(["target_id"], ["knowledge_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_edge_source", "knowledge_edges", ["source_id"])
    op.create_index("ix_knowledge_edge_target", "knowledge_edges", ["target_id"])
    op.create_index("ix_knowledge_edge_source_rel", "knowledge_edges", ["source_id", "relation"])

    # 6. Seed marketing topic profile
    op.execute(
        sa.text("""
        INSERT INTO topic_profiles (id, topic_key, display_name, description, priority, keywords, config, enabled)
        VALUES (
            gen_random_uuid(),
            'marketing',
            'Marketing',
            'Strategy, content, campaigns, posts, and publishing.',
            'critical',
            '["marketing", "content", "social", "brand", "campaign", "publish"]'::jsonb,
            '{}'::jsonb,
            true
        )
        """)
    )


def downgrade() -> None:
    op.drop_table("knowledge_edges")
    op.drop_table("entity_edges")
    op.drop_table("knowledge_nodes")
    op.drop_table("entity_nodes")
    op.drop_table("topic_profiles")
