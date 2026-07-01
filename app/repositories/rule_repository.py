import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import SessionLocal
from app.db.models import RegulationChunkRecord
from app.schemas.rules import RetrievedChunk


class RuleRepository:
    SECTION_KEYWORDS = {
        "Section A": [
            "general",
            "principles",
            "governance",
            "applicable",
            "regulations",
            "code of ethics",
            "disciplinary",
        ],
        "Section B": [
            "unsafe",
            "release",
            "parc",
            "ferme",
            "pit",
            "lane",
            "penalty",
            "stewards",
            "race",
            "qualifying",
            "sprint",
        ],
        "Section C": [
            "plank",
            "wear",
            "thickness",
            "skid",
            "floor",
            "technical",
            "geometry",
            "bodywork",
            "ride",
            "height",
        ],
    }

    def __init__(self) -> None:
        self.chunks_file = Path("data/regulations/processed/chunks.json")
        self._cached_chunks: list[RetrievedChunk] | None = None

    def search_relevant_chunks(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
        chunks = self._load_chunks()
        scored_chunks: list[tuple[int, RetrievedChunk]] = []

        phrases = self._extract_phrases(question)
        keywords = self._expand_keywords(question)
        preferred_sections = self._match_preferred_sections(question)

        for chunk in chunks:
            score = self._score_chunk(
                chunk=chunk,
                phrases=phrases,
                keywords=keywords,
                preferred_sections=preferred_sections,
            )
            if score > 0:
                scored_chunk = chunk.model_copy(update={"score": float(score)})
                scored_chunks.append((score, scored_chunk))

        scored_chunks.sort(key=lambda item: item[0], reverse=True)

        if not scored_chunks:
            return chunks[:1]

        return [chunk for _, chunk in scored_chunks[:top_k]]

    def _load_chunks(self) -> list[RetrievedChunk]:
        if self._cached_chunks is not None:
            return self._cached_chunks

        chunks = self._load_chunks_from_database()
        if chunks:
            self._cached_chunks = chunks
            return self._cached_chunks

        self._cached_chunks = self._load_chunks_from_file()
        return self._cached_chunks

    def _load_chunks_from_database(self) -> list[RetrievedChunk]:
        try:
            with SessionLocal() as session:
                records = session.execute(
                    select(RegulationChunkRecord).order_by(RegulationChunkRecord.id)
                ).scalars().all()
        except SQLAlchemyError:
            return []

        return [
            RetrievedChunk(
                chunk_id=record.chunk_id,
                content=record.content,
                score=None,
                document_title=record.document_title,
                article=record.article,
                page=record.page,
            )
            for record in records
        ]

    def _load_chunks_from_file(self) -> list[RetrievedChunk]:
        with self.chunks_file.open("r", encoding="utf-8") as file:
            chunk_data = json.load(file)

        return [RetrievedChunk(**item) for item in chunk_data]

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
            "plank": ["plank", "wear", "thickness", "skid", "block"],
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

    def _match_preferred_sections(self, question: str) -> list[str]:
        normalized_question = question.lower()
        matched_sections: list[str] = []

        for section, keywords in self.SECTION_KEYWORDS.items():
            if any(keyword in normalized_question for keyword in keywords):
                matched_sections.append(section)

        return matched_sections

    def _score_chunk(
        self,
        chunk: RetrievedChunk,
        phrases: list[str],
        keywords: list[str],
        preferred_sections: list[str],
    ) -> int:
        normalized_content = chunk.content.lower()
        normalized_title = chunk.document_title.lower()
        score = 0

        for phrase in phrases:
            if phrase in normalized_content:
                score += 10

        for keyword in keywords:
            if keyword in normalized_content:
                score += 1

        for section in preferred_sections:
            if section.lower() in normalized_title:
                score += 8

        if chunk.article and any(keyword in chunk.article.lower() for keyword in keywords):
            score += 3

        return score
