from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config.settings import settings


class Base(DeclarativeBase):
    pass


class RegulationChunkRecord(Base):
    """规则切块持久化模型。"""

    __tablename__ = "regulation_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    document_title: Mapped[str] = mapped_column(String(255), index=True)
    section_code: Mapped[str | None] = mapped_column(String(32), index=True)
    article: Mapped[str | None] = mapped_column(String(128), index=True)
    page: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.regulation_embedding_dim)
    )
    chunk_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)
    corpus_version: Mapped[str] = mapped_column(
        String(128), index=True, default="legacy", server_default="legacy"
    )
    document_key: Mapped[str | None] = mapped_column(String(128), index=True)
    article_title: Mapped[str | None] = mapped_column(String(512))
    clause_id: Mapped[str | None] = mapped_column(String(128), index=True)
    chunk_type: Mapped[str] = mapped_column(
        String(32), index=True, default="clause", server_default="clause"
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    embedding_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class RegulationCorpusRecord(Base):
    __tablename__ = "regulation_corpora"

    corpus_version: Mapped[str] = mapped_column(String(128), primary_key=True)
    parser_version: Mapped[str] = mapped_column(String(64))
    source_hashes: Mapped[dict] = mapped_column(JSON)
    build_parameters: Mapped[dict] = mapped_column(JSON)
    embedding_model: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), index=True)
    active: Mapped[bool] = mapped_column(
        Boolean, index=True, default=False, server_default="false"
    )
    validation: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NewsArticleRecord(Base):
    """新闻文章持久化模型。"""

    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint(
            "source_name", "source_article_id", name="uq_news_source_article_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(64), index=True)
    source_article_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_url: Mapped[str] = mapped_column(String(1024), unique=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )


class UserMemoryRecord(Base):
    """用户长期画像/记忆持久化模型。

    按 user_id 维度保存 Agent 长期记忆：
    - constraint / fact / identity 等突变型信息按 memory_key 覆盖旧值；
    - preference / history 等累积型信息通过不同 memory_key 增量追加。
    """

    __tablename__ = "user_memory_items"
    __table_args__ = (
        UniqueConstraint("user_id", "memory_key", name="uq_user_memory_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    memory_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    memory_key: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.7, server_default="0.7")
    source_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    memory_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
