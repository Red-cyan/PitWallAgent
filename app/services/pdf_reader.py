import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from app.schemas.pdf import PdfPage, PdfTable, PdfTextBlock, PdfTextLine
from app.services.text_cleaner import RegulationTextCleaner


class RegulationPdfReader:
    """Extract positioned text and tables, with pypdf as a defensive fallback."""

    def __init__(self, cleaner: RegulationTextCleaner | None = None) -> None:
        self.cleaner = cleaner or RegulationTextCleaner()

    def read_pages(self, pdf_path: str | Path) -> list[PdfPage]:
        path = Path(pdf_path)
        try:
            return self._read_with_pymupdf(path)
        except (ImportError, RuntimeError, ValueError):
            return self._read_with_pypdf(path)

    def _read_with_pymupdf(self, path: Path) -> list[PdfPage]:
        import pymupdf

        document = pymupdf.open(path)
        raw_pages: list[tuple[float, float, list[PdfTextBlock], list[PdfTextLine], list[PdfTable]]] = []
        margin_counts: Counter[str] = Counter()

        for page_number in range(1, len(document) + 1):
            page = document[page_number - 1]
            blocks = [
                PdfTextBlock(text=self.cleaner.clean(str(item[4])), x0=float(item[0]), y0=float(item[1]), x1=float(item[2]), y1=float(item[3]))
                for item in page.get_text("blocks", sort=True)
                if len(item) >= 5 and self.cleaner.clean(str(item[4]))
            ]
            lines = self._extract_lines(page)
            for block in blocks:
                if self._is_margin_block(block, page.rect.height):
                    margin_counts[self._repeat_key(block.text)] += 1
            for line in lines:
                if line.y1 <= page.rect.height * 0.18 or line.y0 >= page.rect.height * 0.86:
                    margin_counts[self._repeat_key(line.text)] += 1
            raw_pages.append((page.rect.width, page.rect.height, blocks, lines, self._extract_tables(page, page_number)))

        repeat_threshold = max(3, round(len(raw_pages) * 0.2))
        repeated = {key for key, count in margin_counts.items() if key and count >= repeat_threshold}
        pages: list[PdfPage] = []
        for page_number, (width, height, blocks, lines, tables) in enumerate(raw_pages, start=1):
            body_blocks = [
                block for block in blocks
                if not self._should_remove_block(block, height, repeated)
            ]
            body_lines = [line for line in lines if not self._should_remove_line(line, height, repeated)]
            pages.append(
                PdfPage(
                    page_number=page_number,
                    text="\n".join(line.text for line in body_lines),
                    width=width,
                    height=height,
                    blocks=body_blocks,
                    lines=body_lines,
                    tables=tables,
                )
            )
        document.close()
        return pages

    def _extract_lines(self, page: object) -> list[PdfTextLine]:
        result: list[PdfTextLine] = []
        data = page.get_text("dict", sort=True)  # type: ignore[attr-defined]
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = self.cleaner.clean("".join(str(span.get("text", "")) for span in spans))
                if not text:
                    continue
                bbox = line.get("bbox", (0, 0, 0, 0))
                sizes = [float(span.get("size", 0)) for span in spans]
                fonts = [str(span.get("font", "")) for span in spans]
                flags = [int(span.get("flags", 0)) for span in spans]
                result.append(PdfTextLine(text=text, y0=float(bbox[1]), y1=float(bbox[3]),
                                          font_size=max(sizes, default=0),
                                          bold=any("bold" in font.lower() or flag & 16 for font, flag in zip(fonts, flags, strict=True))))
        return result

    def _extract_tables(self, page: object, page_number: int) -> list[PdfTable]:
        try:
            finder = page.find_tables()  # type: ignore[attr-defined]
        except Exception:
            return []
        result: list[PdfTable] = []
        for table in finder.tables:
            matrix = table.extract()
            rows = [[self.cleaner.clean(cell or "") for cell in row] for row in matrix]
            rows = [row for row in rows if any(row)]
            if not rows:
                continue
            result.append(PdfTable(page_number=page_number, headers=rows[0], rows=rows[1:]))
        return result

    def _read_with_pypdf(self, path: Path) -> list[PdfPage]:
        reader = PdfReader(str(path))
        return [
            PdfPage(page_number=index, text=self.cleaner.clean(page.extract_text() or ""))
            for index, page in enumerate(reader.pages, start=1)
        ]

    def _is_margin_block(self, block: PdfTextBlock, height: float) -> bool:
        return block.y1 <= height * 0.18 or block.y0 >= height * 0.86

    def _repeat_key(self, text: str) -> str:
        return re.sub(r"\d+", "#", " ".join(text.lower().split()))

    def _should_remove_block(self, block: PdfTextBlock, height: float, repeated: set[str]) -> bool:
        if not self._is_margin_block(block, height):
            return False
        normalized = " ".join(block.text.split())
        if self._repeat_key(normalized) in repeated:
            return True
        return bool(
            re.search(r"©\s*2026|issue\s+\d+|\d{1,2}\s+(january|june|july|december)\s+2026", normalized, re.I)
            or re.fullmatch(r"[A-F]\d{1,3}", normalized)
            or re.fullmatch(r"\d+", normalized)
        )

    def _should_remove_line(self, line: PdfTextLine, height: float, repeated: set[str]) -> bool:
        block = PdfTextBlock(text=line.text, y0=line.y0, y1=line.y1)
        return self._should_remove_block(block, height, repeated)
