from pathlib import Path

from app.schemas.rules import RetrievedChunk
from app.services.chunker import RegulationChunker
from app.services.pdf_reader import RegulationPdfReader


class RuleRepository:
    def __init__(
        self,
        pdf_reader: RegulationPdfReader | None = None,
        chunker: RegulationChunker | None = None,
    ) -> None:
        self.pdf_reader = pdf_reader or RegulationPdfReader()
        self.chunker = chunker or RegulationChunker()
        self.pdf_path = Path(
            "data/regulations/raw/FIA 2026 F1 Regulations - Section A [General Provisions] - Iss 03 - 2026-06-25.pdf"
        )

    def search_relevant_chunks(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
        chunks = self._load_chunks()
        scored_chunks: list[tuple[int, RetrievedChunk]] = []

        keywords = self._extract_keywords(question)
        for chunk in chunks:
            score = self._score_chunk(chunk.content, keywords)
            if score > 0:
                scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda item: item[0], reverse=True)

        if not scored_chunks:
            return chunks[:1]

        return [chunk for _, chunk in scored_chunks[:top_k]]

    def _load_chunks(self) -> list[RetrievedChunk]:
        pages = self.pdf_reader.read_pages(self.pdf_path)
        regulation_chunks = self.chunker.chunk_pages(pages, max_chars=1000)

        return [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=None,
                document_title="FIA 2026 F1 Regulations - Section A [General Provisions]",
                article=self._extract_article(chunk.content),
                page=chunk.page_number,
            )
            for chunk in regulation_chunks
        ]

    def _extract_keywords(self, question: str) -> list[str]:
        return [token.strip(".,?!:;()[]").lower() for token in question.split() if len(token) >= 3]

    def _score_chunk(self, content: str, keywords: list[str]) -> int:
        normalized_content = content.lower()
        return sum(1 for keyword in keywords if keyword in normalized_content)

    def _extract_article(self, content: str) -> str | None:
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("ARTICLE "):
                return line.split(" ", 1)[1]
            if line.startswith("A") and any(char.isdigit() for char in line[:6]):
                token = line.split()[0]
                if token.count(".") >= 1:
                    return token

        return None
