from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Integer, String, Text, func
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
