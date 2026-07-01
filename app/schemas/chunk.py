from pydantic import BaseModel, Field


class RegulationChunk(BaseModel):
    """规则文本切分后的片段。"""

    chunk_id: str = Field(..., description="Unique identifier of the chunk.")
    page_number: int = Field(..., ge=1, description="1-based page number in the PDF.")
    content: str = Field(..., min_length=1, description="Chunk text content.")
