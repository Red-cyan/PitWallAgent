from pydantic import BaseModel, Field


class RegulationChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique identifier of the chunk.")
    document_title: str = Field(..., min_length=1, description="Source document title.")
    section_code: str | None = Field(default=None, description="High-level regulation section code.")
    article: str | None = Field(default=None, description="Closest article heading for the chunk.")
    page_number: int = Field(..., ge=1, description="1-based page number in the PDF.")
    page_start: int | None = Field(default=None, ge=1, description="First source page covered by the chunk.")
    page_end: int | None = Field(default=None, ge=1, description="Last source page covered by the chunk.")
    heading_path: list[str] = Field(default_factory=list, description="Section/article heading path for display.")
    chunk_index: int = Field(..., ge=1, description="1-based chunk index within the page.")
    content: str = Field(..., min_length=1, description="Chunk text content.")
    source_path: str | None = Field(default=None, description="Original PDF path.")
    corpus_version: str = Field(default="legacy", description="Versioned corpus containing this chunk.")
    document_key: str | None = Field(default=None, description="Stable source document key.")
    article_title: str | None = Field(default=None, description="Human-readable article title.")
    clause_id: str | None = Field(default=None, description="Exact regulation clause identifier.")
    chunk_type: str = Field(default="clause", description="clause, table, or article_overview.")
    content_hash: str | None = Field(default=None, description="SHA-256 hash of unmodified display content.")
    embedding_text: str | None = Field(default=None, description="Context-enriched text used for embedding.")
    part_ordinal: int = Field(default=1, ge=1, description="Stable part number within a clause.")
