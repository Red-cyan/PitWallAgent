"""Add clause-aware corpus versioning and atomic activation."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260727_0002"
down_revision: str | None = "20260727_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("regulation_chunks", sa.Column("corpus_version", sa.String(128), server_default="legacy", nullable=False))
    op.add_column("regulation_chunks", sa.Column("document_key", sa.String(128), nullable=True))
    op.add_column("regulation_chunks", sa.Column("article_title", sa.String(512), nullable=True))
    op.add_column("regulation_chunks", sa.Column("clause_id", sa.String(128), nullable=True))
    op.add_column("regulation_chunks", sa.Column("chunk_type", sa.String(32), server_default="clause", nullable=False))
    op.add_column("regulation_chunks", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column("regulation_chunks", sa.Column("embedding_text", sa.Text(), nullable=True))
    for column in ("corpus_version", "document_key", "clause_id", "chunk_type", "content_hash"):
        op.create_index(f"ix_regulation_chunks_{column}", "regulation_chunks", [column])

    op.create_table(
        "regulation_corpora",
        sa.Column("corpus_version", sa.String(128), primary_key=True),
        sa.Column("parser_version", sa.String(64), nullable=False),
        sa.Column("source_hashes", sa.JSON(), nullable=False),
        sa.Column("build_parameters", sa.JSON(), nullable=False),
        sa.Column("embedding_model", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_regulation_corpora_status", "regulation_corpora", ["status"])
    op.create_index("ix_regulation_corpora_active", "regulation_corpora", ["active"])
    op.execute(
        "INSERT INTO regulation_corpora "
        "(corpus_version, parser_version, source_hashes, build_parameters, status, active) "
        "SELECT 'legacy', 'page-chunker-v1', '{}', '{\"legacy\": true}', 'validated', false "
        "WHERE EXISTS (SELECT 1 FROM regulation_chunks WHERE corpus_version = 'legacy')"
    )


def downgrade() -> None:
    op.drop_table("regulation_corpora")
    for column in ("embedding_text", "content_hash", "chunk_type", "clause_id", "article_title", "document_key", "corpus_version"):
        op.drop_column("regulation_chunks", column)
