from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.pdf import PdfTable


class RegulationClause(BaseModel):
    clause_id: str
    title: str | None = None
    article_id: str
    article_title: str | None = None
    level: int = Field(..., ge=1)
    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)
    paragraphs: list[str] = Field(default_factory=list)
    list_items: list[str] = Field(default_factory=list)
    tables: list[PdfTable] = Field(default_factory=list)
    scope: str | None = None

    @property
    def content(self) -> str:
        heading = " ".join(part for part in (self.clause_id, self.title) if part)
        return "\n\n".join([heading, *self.paragraphs, *self.list_items]).strip()


class RegulationArticle(BaseModel):
    article_id: str
    title: str | None = None
    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)
    clauses: list[RegulationClause] = Field(default_factory=list)
    scope: str | None = None


class RegulationDocument(BaseModel):
    document_key: str
    document_title: str
    section_code: str
    source_path: str | None = None
    page_count: int = Field(..., ge=0)
    articles: list[RegulationArticle] = Field(default_factory=list)


class CorpusValidation(BaseModel):
    valid: bool
    clause_missing_rate: float = 0
    body_coverage_rate: float = 1
    false_header_clauses: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CorpusManifest(BaseModel):
    corpus_version: str
    parser_version: str
    source_hashes: dict[str, str]
    chunk_max_chars: int
    embedding_model: str | None = None
    status: Literal["building", "validated", "failed", "active"] = "building"
    active: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    validation: CorpusValidation | None = None
