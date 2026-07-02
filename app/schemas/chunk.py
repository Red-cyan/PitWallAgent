from pydantic import BaseModel, Field


class RegulationChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique identifier of the chunk.")
    document_title: str = Field(..., min_length=1, description="Source document title.")
    section_code: str | None = Field(default=None, description="High-level regulation section code.")
    article: str | None = Field(default=None, description="Closest article heading for the chunk.")
    page_number: int = Field(..., ge=1, description="1-based page number in the PDF.")
    chunk_index: int = Field(..., ge=1, description="1-based chunk index within the page.")
    content: str = Field(..., min_length=1, description="Chunk text content.")
    source_path: str | None = Field(default=None, description="Original PDF path.")
