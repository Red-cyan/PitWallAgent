from pydantic import BaseModel, Field


class PdfPage(BaseModel):
    """PDF 单页文本。"""

    page_number: int = Field(..., ge=1, description="1-based page number in the PDF.")
    text: str = Field(..., description="Extracted text content of the page.")
