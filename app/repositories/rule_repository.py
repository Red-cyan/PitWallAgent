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
        self.pdf_directory = Path("data/regulations/raw")
        self._cached_chunks: list[RetrievedChunk] | None = None

    def search_relevant_chunks(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
        chunks = self._load_chunks()
        scored_chunks: list[tuple[int, RetrievedChunk]] = []

        phrases = self._extract_phrases(question)
        keywords = self._expand_keywords(question)

        for chunk in chunks:
            score = self._score_chunk(chunk.content, phrases, keywords)
            if score > 0:
                scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda item: item[0], reverse=True)

        if not scored_chunks:
            return chunks[:1]

        return [chunk for _, chunk in scored_chunks[:top_k]]

    def _load_chunks(self) -> list[RetrievedChunk]:
        if self._cached_chunks is not None:
            return self._cached_chunks

        retrieved_chunks: list[RetrievedChunk] = []

        for pdf_path in sorted(self.pdf_directory.glob("*.pdf")):
            pages = self.pdf_reader.read_pages(pdf_path)
            regulation_chunks = self.chunker.chunk_pages(pages, max_chars=1000)
            document_title = pdf_path.stem

            for chunk in regulation_chunks:
                retrieved_chunks.append(
                    RetrievedChunk(
                        chunk_id=f"{document_title}:{chunk.chunk_id}",
                        content=chunk.content,
                        score=None,
                        document_title=document_title,
                        article=self._extract_article(chunk.content),
                        page=chunk.page_number,
                    )
                )

        self._cached_chunks = retrieved_chunks
        return self._cached_chunks

    def _extract_phrases(self, question: str) -> list[str]:
        normalized_question = question.lower()
        phrases: list[str] = []

        if "parc ferme" in normalized_question or "parc fermé" in normalized_question:
            phrases.append("parc ferme")

        if "unsafe release" in normalized_question:
            phrases.append("unsafe release")

        return phrases

    def _expand_keywords(self, question: str) -> list[str]:
        raw_tokens = [
            token.strip(".,?!:;()[]").lower()
            for token in question.split()
            if len(token.strip(".,?!:;()[]")) >= 3
        ]

        keyword_map = {
            "breaches": ["breach", "breaches", "sanctions", "adjudication", "investigations"],
            "breach": ["breach", "breaches", "sanctions", "adjudication", "investigations"],
            "handled": ["handled", "handling", "adjudication", "sanctions", "investigations"],
            "unsafe": ["unsafe", "danger", "endanger", "risk"],
            "release": ["release", "released", "pit"],
            "parc": ["parc", "ferme", "restricted"],
            "ferme": ["parc", "ferme", "restricted"],
            "principles": ["principles", "overview", "application"],
            "general": ["general", "principles", "application"],
        }

        expanded_keywords: list[str] = []
        for token in raw_tokens:
            expanded_keywords.extend(keyword_map.get(token, [token]))

        seen: set[str] = set()
        unique_keywords: list[str] = []
        for keyword in expanded_keywords:
            if keyword not in seen:
                seen.add(keyword)
                unique_keywords.append(keyword)

        return unique_keywords

    def _score_chunk(self, content: str, phrases: list[str], keywords: list[str]) -> int:
        normalized_content = content.lower()
        score = 0

        for phrase in phrases:
            if phrase in normalized_content:
                score += 10

        for keyword in keywords:
            if keyword in normalized_content:
                score += 1

        return score

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
