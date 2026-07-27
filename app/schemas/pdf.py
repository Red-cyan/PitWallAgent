from pydantic import BaseModel, Field


class PdfTextBlock(BaseModel):
    text: str
    x0: float = 0
    y0: float = 0
    x1: float = 0
    y1: float = 0


class PdfTextLine(BaseModel):
    text: str
    y0: float = 0
    y1: float = 0
    font_size: float = 0
    bold: bool = False


class PdfTable(BaseModel):
    page_number: int = Field(..., ge=1)
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class PdfPage(BaseModel):
    """PDF 单页文本。"""

    page_number: int = Field(..., ge=1, description="1-based page number in the PDF.")
    text: str = Field(..., description="Extracted text content of the page.")
    width: float | None = None
    height: float | None = None
    blocks: list[PdfTextBlock] = Field(default_factory=list)
    lines: list[PdfTextLine] = Field(default_factory=list)
    tables: list[PdfTable] = Field(default_factory=list)
