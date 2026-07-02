from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
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
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.regulation_embedding_dim))
    chunk_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class NewsArticleRecord(Base):
    """新闻文章持久化模型。"""

    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("source_name", "source_article_id", name="uq_news_source_article_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(64), index=True)
    source_article_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_url: Mapped[str] = mapped_column(String(1024), unique=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
