from pathlib import Path

from pypdf import PdfReader

from app.schemas.pdf import PdfPage
from app.services.text_cleaner import RegulationTextCleaner


class RegulationPdfReader:
    def __init__(self, cleaner: RegulationTextCleaner | None = None) -> None:
        self.cleaner = cleaner or RegulationTextCleaner()

    def read_pages(self, pdf_path: str | Path) -> list[PdfPage]:
        path = Path(pdf_path)
        reader = PdfReader(str(path))

        pages: list[PdfPage] = []
        for index, page in enumerate(reader.pages, start=1):
            pages.append(
                PdfPage(
                    page_number=index,
                    text=self.cleaner.clean(page.extract_text() or ""),
                )
            )

        return pages
