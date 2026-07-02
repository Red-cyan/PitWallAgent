import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import SessionLocal
from app.db.models import RegulationChunkRecord
from app.rag.retrieval.query_rewriter import QueryRewriter
from app.schemas.rules import RetrievalDebugResponse, RetrievedChunk


class RuleRepository:
    VECTOR_CANDIDATE_LIMIT = 12
    MIN_RERANK_SCORE = 2
    QUERY_SYNONYMS = {
        "红旗": "red flag",
        "黄旗": "yellow flag",
        "安全车": "safety car",
        "虚拟安全车": "virtual safety car vsc",
        "封闭维修区": "parc ferme",
        "封闭维修": "parc ferme",
        "不安全释放": "unsafe release",
        "违规释放": "unsafe release",
        "底板": "plank",
        "木板": "plank",
    }

    SECTION_KEYWORDS = {
        "Section A": [
            "general",
            "principles",
            "governance",
            "applicable",
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
            "red",
            "flag",
            "yellow",
            "safety",
            "vsc",
            "virtual safety car",
            "suspension",
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

    def __init__(self, query_rewriter: QueryRewriter | None = None) -> None:
        self.chunks_file = Path("data/regulations/processed/chunks.json")
        self._cached_chunks: list[RetrievedChunk] | None = None
        self.query_rewriter = query_rewriter or QueryRewriter()

    def search_relevant_chunks(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
        debug_data = self.debug_retrieval(question=question, top_k=top_k)
        return debug_data.retrieved_chunks

    def debug_retrieval(self, question: str, top_k: int = 3) -> RetrievalDebugResponse:
        normalized_question = self._normalize_question(question)
        rewritten_queries = self.query_rewriter.rewrite(question)
        retrieval_questions = self._deduplicate_queries([normalized_question, *rewritten_queries])
        scoring_question = " ".join(retrieval_questions)
        phrases = self._extract_phrases(scoring_question)
        keywords = self._expand_keywords(scoring_question)
        preferred_sections = self._match_preferred_sections(scoring_question)
        chunks = self._retrieve_candidate_chunks(
            retrieval_questions,
            top_k=top_k,
            phrases=phrases,
            keywords=keywords,
            preferred_sections=preferred_sections,
        )
        scored_chunks = self._rerank_chunks(
            chunks=chunks,
            top_k=top_k,
            phrases=phrases,
            keywords=keywords,
            preferred_sections=preferred_sections,
        )
        return RetrievalDebugResponse(
            question=question,
            normalized_question=normalized_question,
            rewritten_queries=rewritten_queries,
            retrieval_queries=retrieval_questions,
            extracted_phrases=phrases,
            expanded_keywords=keywords,
            preferred_sections=preferred_sections,
            retrieved_chunks=scored_chunks,
        )

    def _rerank_chunks(
        self,
        chunks: list[RetrievedChunk],
        top_k: int,
        phrases: list[str],
        keywords: list[str],
        preferred_sections: list[str],
    ) -> list[RetrievedChunk]:
        scored_chunks: list[tuple[int, RetrievedChunk]] = []

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
            return []

        strong_chunks = [
            chunk
            for score, chunk in scored_chunks
            if score >= self.MIN_RERANK_SCORE
        ]
        return strong_chunks[:top_k]

    def _normalize_question(self, question: str) -> str:
        normalized_question = question

        for source, target in self.QUERY_SYNONYMS.items():
            if source in normalized_question and target not in normalized_question.lower():
                normalized_question = f"{normalized_question} {target}"

        return normalized_question

    def _deduplicate_queries(self, queries: list[str]) -> list[str]:
        unique_queries: list[str] = []
        seen: set[str] = set()

        for query in queries:
            normalized = query.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            unique_queries.append(normalized)

        return unique_queries

    def _retrieve_candidate_chunks(
        self,
        questions: list[str],
        top_k: int,
        phrases: list[str],
        keywords: list[str],
        preferred_sections: list[str],
    ) -> list[RetrievedChunk]:
        vector_chunks = self._search_by_vector_queries(
            questions,
            top_k=max(top_k, self.VECTOR_CANDIDATE_LIMIT),
        )
        keyword_chunks = self._search_by_keywords(
            phrases=phrases,
            keywords=keywords,
            preferred_sections=preferred_sections,
            top_k=max(top_k, self.VECTOR_CANDIDATE_LIMIT),
        )

        chunks = self._merge_candidates(vector_chunks, keyword_chunks, top_k=self.VECTOR_CANDIDATE_LIMIT)
        if chunks:
            filtered_chunks = self._filter_chunks_by_section(chunks, preferred_sections)
            if filtered_chunks:
                return filtered_chunks
            return chunks

        return []

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
                section=record.section_code,
                page=record.page,
            )
            for record in records
        ]

    def _load_chunks_from_file(self) -> list[RetrievedChunk]:
        with self.chunks_file.open("r", encoding="utf-8") as file:
            chunk_data = json.load(file)

        return [RetrievedChunk(**item) for item in chunk_data]

    def _search_by_vector_queries(self, questions: list[str], top_k: int) -> list[RetrievedChunk]:
        merged_chunks: list[RetrievedChunk] = []
        seen_chunk_ids: set[str] = set()

        for question in questions:
            for chunk in self._search_by_vector(question, top_k):
                if chunk.chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk.chunk_id)
                merged_chunks.append(chunk)

                if len(merged_chunks) >= top_k:
                    return merged_chunks

        return merged_chunks

    def _search_by_vector(self, question: str, top_k: int) -> list[RetrievedChunk]:
        try:
            from app.rag.embedding.factory import build_embedding_service

            embedding_service = build_embedding_service()
            question_embedding = embedding_service.embed_texts([question])[0]
        except Exception:
            return []

        try:
            with SessionLocal() as session:
                records = session.execute(
                    select(RegulationChunkRecord)
                    .where(RegulationChunkRecord.embedding.is_not(None))
                    .order_by(RegulationChunkRecord.embedding.cosine_distance(question_embedding))
                    .limit(top_k)
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
                section=record.section_code,
                page=record.page,
            )
            for record in records
        ]

    def _search_by_keywords(
        self,
        phrases: list[str],
        keywords: list[str],
        preferred_sections: list[str],
        top_k: int,
    ) -> list[RetrievedChunk]:
        scored_chunks: list[tuple[int, RetrievedChunk]] = []

        for chunk in self._load_chunks():
            score = self._score_chunk(
                chunk=chunk,
                phrases=phrases,
                keywords=keywords,
                preferred_sections=preferred_sections,
            )
            if score > 0:
                scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored_chunks[:top_k]]

    def _merge_candidates(
        self,
        primary_chunks: list[RetrievedChunk],
        secondary_chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        merged_chunks: list[RetrievedChunk] = []
        seen_chunk_ids: set[str] = set()

        for chunk in [*primary_chunks, *secondary_chunks]:
            if chunk.chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk.chunk_id)
            merged_chunks.append(chunk)

            if len(merged_chunks) >= top_k:
                break

        return merged_chunks

    def _extract_phrases(self, question: str) -> list[str]:
        normalized_question = question.lower()
        phrases: list[str] = []

        if "parc ferme" in normalized_question or "parc fermé" in normalized_question:
            phrases.append("parc ferme")

        if "unsafe release" in normalized_question:
            phrases.append("unsafe release")

        if "red flag" in normalized_question:
            phrases.append("red flag")

        if "yellow flag" in normalized_question:
            phrases.append("yellow flag")

        if "safety car" in normalized_question:
            phrases.append("safety car")

        if "virtual safety car" in normalized_question or " vsc" in normalized_question:
            phrases.append("virtual safety car")

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
            "red": ["red", "flag", "suspension", "stopped"],
            "yellow": ["yellow", "flag", "warning", "marshal"],
            "flag": ["red", "yellow", "flag", "suspension", "stopped"],
            "safety": ["safety", "car", "vsc", "deployment"],
            "virtual": ["virtual", "safety", "car", "vsc"],
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

    def _filter_chunks_by_section(
        self,
        chunks: list[RetrievedChunk],
        preferred_sections: list[str],
    ) -> list[RetrievedChunk]:
        if not preferred_sections:
            return chunks

        filtered = [
            chunk
            for chunk in chunks
            if any(section.lower() in chunk.document_title.lower() for section in preferred_sections)
        ]
        return filtered or chunks

    def _score_chunk(
        self,
        chunk: RetrievedChunk,
        phrases: list[str],
        keywords: list[str],
        preferred_sections: list[str],
    ) -> int:
        normalized_content = chunk.content.lower()
        normalized_title = chunk.document_title.lower()
        content_score = 0

        for phrase in phrases:
            if phrase in normalized_content:
                content_score += 10

        for keyword in keywords:
            if keyword in normalized_content:
                content_score += 1

        if chunk.article and any(keyword in chunk.article.lower() for keyword in keywords):
            content_score += 3

        if content_score == 0:
            return 0

        score = content_score
        for section in preferred_sections:
            if section.lower() in normalized_title:
                score += 8

        return score
