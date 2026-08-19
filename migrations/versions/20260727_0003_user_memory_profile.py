"""Add user-scoped long-term memory profile in PostgreSQL.

Revision ID: 20260727_0003
Revises: 20260727_0002
Create Date: 2026-07-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260727_0003"
down_revision: str | None = "20260727_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_memory_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("memory_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("memory_key", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.7", nullable=False),
        sa.Column("source_session_id", sa.String(length=128), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "memory_key", name="uq_user_memory_key"),
    )
    op.create_index(
        "ix_user_memory_items_memory_id",
        "user_memory_items",
        ["memory_id"],
        unique=True,
    )
    op.create_index("ix_user_memory_items_user_id", "user_memory_items", ["user_id"])
    op.create_index("ix_user_memory_items_category", "user_memory_items", ["category"])


def downgrade() -> None:
    op.drop_index("ix_user_memory_items_category", table_name="user_memory_items")
    op.drop_index("ix_user_memory_items_user_id", table_name="user_memory_items")
    op.drop_index("ix_user_memory_items_memory_id", table_name="user_memory_items")
    op.drop_table("user_memory_items")
