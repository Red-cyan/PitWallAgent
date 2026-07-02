import re
from pathlib import Path

from app.schemas.chunk import RegulationChunk
from app.schemas.pdf import PdfPage


class RegulationChunker:
    SECTION_PATTERN = re.compile(r"(Section\s+[A-F])", re.IGNORECASE)
    ARTICLE_PATTERN = re.compile(
        r"^(ARTICLE\s+\d+[A-Z]?(?:\.\d+)*|[A-F]\d+(?:\.\d+)*)\b",
        re.IGNORECASE,
    )

    def chunk_pages(self, pages: list[PdfPage], max_chars: int = 1000) -> list[RegulationChunk]:
        return self.chunk_document(
            document_title="Unknown document",
            pages=pages,
            max_chars=max_chars,
        )

    def chunk_document(
        self,
        document_title: str,
        pages: list[PdfPage],
        max_chars: int = 1000,
        source_path: str | Path | None = None,
    ) -> list[RegulationChunk]:
        chunks: list[RegulationChunk] = []
        section_code = self._extract_section_code(document_title)
        normalized_source_path = str(source_path) if source_path is not None else None

        for page in pages:
            text = page.text.strip()
            if not text or self._should_skip_page(text):
                continue

            chunks.extend(
                self._chunk_page(
                    document_title=document_title,
                    section_code=section_code,
                    page=page,
                    max_chars=max_chars,
                    source_path=normalized_source_path,
                )
            )

        return chunks

    def _chunk_page(
        self,
        document_title: str,
        section_code: str | None,
        page: PdfPage,
        max_chars: int,
        source_path: str | None,
    ) -> list[RegulationChunk]:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        if not lines:
            return []

        page_chunks: list[RegulationChunk] = []
        current_article: str | None = None
        current_lines: list[str] = []
        current_length = 0
        chunk_index = 1

        def flush() -> None:
            nonlocal current_lines, current_length, chunk_index
            content = "\n".join(current_lines).strip()
            if not content:
                return
            page_chunks.append(
                RegulationChunk(
                    chunk_id=self._build_chunk_id(document_title, page.page_number, chunk_index),
                    document_title=document_title,
                    section_code=section_code,
                    article=current_article,
                    page_number=page.page_number,
                    chunk_index=chunk_index,
                    content=content,
                    source_path=source_path,
                )
            )
            current_lines = []
            current_length = 0
            chunk_index += 1

        for line in lines:
            article = self._extract_article_from_line(line)
            if article and current_lines:
                flush()
            if article:
                current_article = article

            if len(line) > max_chars:
                if current_lines:
                    flush()
                for part in self._split_text(line, max_chars=max_chars):
                    current_lines = [part]
                    current_length = len(part)
                    flush()
                continue

            projected_length = current_length + len(line) + (1 if current_lines else 0)
            if projected_length > max_chars and current_lines:
                flush()

            current_lines.append(line)
            current_length += len(line) + 1

        flush()
        return page_chunks

    def _should_skip_page(self, text: str) -> bool:
        upper_text = text.upper()

        if "CONTENTS:" in upper_text:
            return True

        if "CONVENTION:" in upper_text:
            return True

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return True

        index_like_count = sum(1 for line in lines if self._looks_like_index_entry(line))
        sentence_like_count = sum(1 for line in lines if line.endswith(".") and len(line) > 60)

        return index_like_count >= 10 and sentence_like_count <= 2

    def _looks_like_index_entry(self, line: str) -> bool:
        tokens = line.split()
        if not tokens:
            return False

        first_token = tokens[0]
        if line.startswith("ARTICLE ") or line.startswith("APPENDIX "):
            return line[-1].isdigit()

        return first_token.startswith("A") and any(char.isdigit() for char in first_token) and line[-1].isdigit()

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

    def _extract_section_code(self, document_title: str) -> str | None:
        match = self.SECTION_PATTERN.search(document_title)
        return match.group(1).title() if match else None

    def _extract_article_from_line(self, line: str) -> str | None:
        match = self.ARTICLE_PATTERN.match(line.strip())
        if not match:
            return None
        return match.group(1).upper()

    def _build_chunk_id(self, document_title: str, page_number: int, chunk_index: int) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", document_title.lower()).strip("-")
        return f"{slug}-p{page_number}-c{chunk_index}"
