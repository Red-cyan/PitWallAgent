"""Create the initial PitWall schema and adopt pre-Alembic databases."""

from collections.abc import Sequence

from alembic import context, op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


revision: str = "20260727_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    existing_tables = (
        set()
        if context.is_offline_mode()
        else set(sa.inspect(op.get_bind()).get_table_names())
    )

    if "regulation_chunks" not in existing_tables:
        _create_regulation_chunks()
    if "news_articles" not in existing_tables:
        _create_news_articles()
    else:
        op.execute(
            "ALTER TABLE news_articles "
            "ALTER COLUMN source_article_id TYPE VARCHAR(255)"
        )


def _create_regulation_chunks() -> None:
    op.create_table(
        "regulation_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chunk_id", sa.String(length=255), nullable=False),
        sa.Column("document_title", sa.String(length=255), nullable=False),
        sa.Column("section_code", sa.String(length=32), nullable=True),
        sa.Column("article", sa.String(length=128), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regulation_chunks_chunk_id", "regulation_chunks", ["chunk_id"], unique=True)
    op.create_index("ix_regulation_chunks_document_title", "regulation_chunks", ["document_title"])
    op.create_index("ix_regulation_chunks_section_code", "regulation_chunks", ["section_code"])
    op.create_index("ix_regulation_chunks_article", "regulation_chunks", ["article"])


def _create_news_articles() -> None:
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_article_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("article_url", sa.String(length=1024), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_url"),
        sa.UniqueConstraint("source_name", "source_article_id", name="uq_news_source_article_id"),
    )
    op.create_index("ix_news_articles_source_name", "news_articles", ["source_name"])
    op.create_index("ix_news_articles_title", "news_articles", ["title"])
    op.create_index("ix_news_articles_published_at", "news_articles", ["published_at"])


def downgrade() -> None:
    op.drop_table("news_articles")
    op.drop_table("regulation_chunks")
