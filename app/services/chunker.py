from app.schemas.chunk import RegulationChunk
from app.schemas.pdf import PdfPage


class RegulationChunker:
    def chunk_pages(self, pages: list[PdfPage], max_chars: int = 1000) -> list[RegulationChunk]:
        chunks: list[RegulationChunk] = []

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            parts = self._split_text(text, max_chars=max_chars)
            for index, part in enumerate(parts, start=1):
                chunks.append(
                    RegulationChunk(
                        chunk_id=f"page-{page.page_number}-chunk-{index}",
                        page_number=page.page_number,
                        content=part,
                    )
                )

        return chunks

    def _split_text(self, text: str, max_chars: int) -> list[str]:
        if len(text) <= max_chars:
            return [text]

        parts: list[str] = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = min(start + max_chars, text_length)
            if end < text_length:
                split_at = text.rfind(" ", start, end)
                if split_at > start:
                    end = split_at

            parts.append(text[start:end].strip())
            start = end

        return [part for part in parts if part]
