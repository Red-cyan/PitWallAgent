from pydantic import BaseModel, Field


class RegulationDocumentIngestionResult(BaseModel):
    document_title: str = Field(..., min_length=1, description="Source document title.")
    source_path: str = Field(..., min_length=1, description="Source PDF path.")
    section_code: str | None = Field(default=None, description="High-level section code inferred from the title.")
    page_count: int = Field(..., ge=0, description="Number of parsed PDF pages.")
    chunk_count: int = Field(..., ge=0, description="Number of chunks generated for this document.")
    embedded_chunk_count: int = Field(..., ge=0, description="Number of chunks with generated embeddings.")


class RegulationIngestionSummary(BaseModel):
    document_count: int = Field(..., ge=0, description="Number of ingested documents.")
    chunk_count: int = Field(..., ge=0, description="Total number of generated chunks.")
    embedded_chunk_count: int = Field(..., ge=0, description="Total number of chunks with embeddings.")
    output_path: str | None = Field(default=None, description="Path to the generated chunk manifest.")
    documents: list[RegulationDocumentIngestionResult] = Field(
        default_factory=list,
        description="Per-document ingestion results.",
    )
