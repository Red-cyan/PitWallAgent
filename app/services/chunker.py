from app.schemas.chunk import RegulationChunk
from app.schemas.pdf import PdfPage


class RegulationChunker:
    def chunk_pages(self, pages: list[PdfPage], max_chars: int = 1000) -> list[RegulationChunk]:
        chunks: list[RegulationChunk] = []

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            if self._should_skip_page(text):
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

    def _should_skip_page(self, text: str) -> bool:
        upper_text = text.upper()

        if "CONTENTS:" in upper_text:
            return True

        if "CONVENTION:" in upper_text:
            return True

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return True

        index_like_count = sum(
            1
            for line in lines
            if self._looks_like_index_entry(line)
        )
        sentence_like_count = sum(
            1 for line in lines if line.endswith(".") and len(line) > 60
        )

        if index_like_count >= 10 and sentence_like_count <= 2:
            return True

        return False

    def _looks_like_index_entry(self, line: str) -> bool:
        tokens = line.split()
        if not tokens:
            return False

        first_token = tokens[0]
        if line.startswith("ARTICLE ") or line.startswith("APPENDIX "):
            return line[-1].isdigit()

        return (
            first_token.startswith("A")
            and any(char.isdigit() for char in first_token)
            and line[-1].isdigit()
        )

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
