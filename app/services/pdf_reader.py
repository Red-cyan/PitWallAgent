from pathlib import Path

from pypdf import PdfReader

from app.schemas.pdf import PdfPage


class RegulationPdfReader:
    def read_pages(self, pdf_path: str | Path) -> list[PdfPage]:
        path = Path(pdf_path)
        reader = PdfReader(str(path))

        pages: list[PdfPage] = []
        for index, page in enumerate(reader.pages, start=1):
            pages.append(
                PdfPage(
                    page_number=index,
                    text=(page.extract_text() or "").strip(),
                )
            )

        return pages
