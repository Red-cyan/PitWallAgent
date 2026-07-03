import json
import math
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import SessionLocal
from app.db.models import RegulationChunkRecord
from app.rag.retrieval.query_rewriter import QueryRewriter
from app.schemas.rules import RetrievalDebugResponse, RetrievedChunk


class RuleRepository:
    VECTOR_CANDIDATE_LIMIT = 40
    KEYWORD_CANDIDATE_LIMIT = 40
    HYBRID_CANDIDATE_LIMIT = 50
    MIN_RERANK_SCORE = 8
    PARTIAL_RERANK_SCORE = 1
    MIN_KEYWORD_EVIDENCE_SCORE = 6
    RRF_K = 60
    QUERY_SYNONYMS = {
        "红旗": "red flag",
        "黄旗": "yellow flag",
        "安全车": "safety car",
        "虚拟安全车": "virtual safety car vsc",
        "封闭维修区": "parc ferme",
        "封闭维修": "parc ferme",
        "不安全释放": "unsafe release",
        "违规释放": "unsafe release",
        "维修区超速": "pit lane speed limit speeding penalty",
        "维修区限速": "pit lane speed limit",
        "维修区速度": "pit lane speed limit",
        "危险驾驶": "dangerous driving penalty stewards incident",
        "危险返回赛道": "dangerous rejoin track penalty stewards",
        "不安全驾驶": "dangerous driving penalty stewards incident",
        "赛会干事": "stewards penalty investigation",
        "干事调查": "stewards investigation penalty",
        "处罚": "penalty sanctions stewards",
        "罚时": "time penalty stewards",
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
            "dangerous",
            "driving",
            "incident",
            "investigation",
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

    def get_section_chunks(self, section_code: str, limit: int = 6) -> list[RetrievedChunk]:
        normalized_section = self._normalize_section_code(section_code)
        chunks = [
            chunk
            for chunk in self._load_chunks()
            if self._chunk_section_code(chunk) == normalized_section
        ]
        return self._select_representative_section_chunks(chunks, limit=limit)

    def get_document_overview_chunks(self, limit_per_section: int = 1) -> list[RetrievedChunk]:
        overview_chunks: list[RetrievedChunk] = []
        for section_code in ("Section A", "Section B", "Section C", "Section D", "Section E", "Section F"):
            overview_chunks.extend(self.get_section_chunks(section_code, limit=limit_per_section))
        return overview_chunks

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
        vector_candidates = chunks["vector"]
        keyword_candidates = chunks["keyword"]
        hybrid_candidates = chunks["hybrid"]
        scored_chunks = self._rerank_chunks(
            chunks=hybrid_candidates,
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
            vector_candidates=vector_candidates,
            keyword_candidates=keyword_candidates,
            hybrid_candidates=hybrid_candidates,
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
        scored_chunks: list[tuple[float, RetrievedChunk]] = []

        for chunk in chunks:
            score = self._score_chunk(
                chunk=chunk,
                phrases=phrases,
                keywords=keywords,
                preferred_sections=preferred_sections,
            )
            phrase_matches = self._count_phrase_matches(chunk, phrases)
            hybrid_score = min(chunk.score or 0.0, 25.0)
            final_score = score + hybrid_score
            if final_score > 0:
                is_strong = (
                    final_score >= self.MIN_RERANK_SCORE
                    and (phrase_matches > 0 or score >= self.MIN_KEYWORD_EVIDENCE_SCORE)
                )
                scored_chunk = chunk.model_copy(
                    update={
                        "score": float(final_score),
                        "score_components": {
                            **chunk.score_components,
                            "rerank_keyword": float(score),
                            "rerank_phrase_matches": float(phrase_matches),
                            "rerank_hybrid": round(hybrid_score, 4),
                            "rerank_final": round(final_score, 4),
                            "evidence_strength": 1.0 if is_strong else 0.0,
                        },
                    }
                )
                scored_chunks.append((final_score, scored_chunk))

        scored_chunks.sort(key=lambda item: item[0], reverse=True)

        if not scored_chunks:
            return []

        strong_chunks = [
            chunk
            for score, chunk in scored_chunks
            if score >= self.MIN_RERANK_SCORE
            and chunk.score_components.get("evidence_strength") == 1.0
        ]
        if strong_chunks:
            return strong_chunks[:top_k]

        weak_chunks = [
            chunk
            for score, chunk in scored_chunks
            if score >= self.PARTIAL_RERANK_SCORE
        ]
        return weak_chunks[:top_k]

    def _normalize_question(self, question: str) -> str:
        normalized_question = question
        normalized_question = re.sub(
            r"(?<![a-z])section\s*([a-f])(?![a-z])",
            lambda match: f"Section {match.group(1).upper()}",
            normalized_question,
            flags=re.IGNORECASE,
        )

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
    ) -> dict[str, list[RetrievedChunk]]:
        vector_chunks = self._search_by_vector_queries(
            questions,
            top_k=max(top_k, self.VECTOR_CANDIDATE_LIMIT),
        )
        keyword_chunks = self._search_by_keywords(
            phrases=phrases,
            keywords=keywords,
            preferred_sections=preferred_sections,
            top_k=max(top_k, self.KEYWORD_CANDIDATE_LIMIT),
        )

        chunks = self._fuse_candidates(vector_chunks, keyword_chunks, top_k=self.HYBRID_CANDIDATE_LIMIT)
        if chunks:
            filtered_chunks = self._filter_chunks_by_section(chunks, preferred_sections)
            if filtered_chunks:
                chunks = filtered_chunks

        return {
            "vector": vector_chunks,
            "keyword": keyword_chunks,
            "hybrid": chunks,
        }

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
                page_start=(record.chunk_metadata or {}).get("page_start") or record.page,
                page_end=(record.chunk_metadata or {}).get("page_end") or record.page,
                heading_path=(record.chunk_metadata or {}).get("heading_path") or [],
            )
            for record in records
        ]

    def _load_chunks_from_file(self) -> list[RetrievedChunk]:
        with self.chunks_file.open("r", encoding="utf-8") as file:
            chunk_data = json.load(file)

        return [RetrievedChunk(**item) for item in chunk_data]

    def _normalize_section_code(self, section_code: str) -> str:
        match = re.search(r"section\s*([a-f])", section_code, flags=re.IGNORECASE)
        if match:
            return f"Section {match.group(1).upper()}"
        match = re.fullmatch(r"\s*([a-f])\s*", section_code, flags=re.IGNORECASE)
        if not match:
            return section_code
        return f"Section {match.group(1).upper()}"

    def _chunk_section_code(self, chunk: RetrievedChunk) -> str:
        if chunk.section:
            return self._normalize_section_code(chunk.section)
        match = re.search(r"Section\s*([A-F])", chunk.document_title, flags=re.IGNORECASE)
        if match:
            return f"Section {match.group(1).upper()}"
        return ""

    def _select_representative_section_chunks(
        self,
        chunks: list[RetrievedChunk],
        limit: int,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []

        selected: list[RetrievedChunk] = []
        seen_articles: set[str] = set()

        for chunk in chunks:
            article = chunk.article or ""
            if not article or article in seen_articles:
                continue
            if not re.fullmatch(r"[A-F]\d+(?:\.\d+)?", article, flags=re.IGNORECASE):
                continue
            seen_articles.add(article)
            selected.append(chunk.model_copy(update={"score": chunk.score or 1.0}))
            if len(selected) >= limit:
                return selected

        for chunk in chunks:
            if chunk.chunk_id in {selected_chunk.chunk_id for selected_chunk in selected}:
                continue
            selected.append(chunk.model_copy(update={"score": chunk.score or 1.0}))
            if len(selected) >= limit:
                break

        return selected

    def _search_by_vector_queries(self, questions: list[str], top_k: int) -> list[RetrievedChunk]:
        merged_chunks: list[RetrievedChunk] = []
        seen_chunk_ids: set[str] = set()

        for question in questions:
            for chunk in self._search_by_vector(question, top_k):
                if chunk.chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk.chunk_id)
                merged_chunks.append(chunk)

        merged_chunks.sort(key=lambda chunk: chunk.score or 0, reverse=True)
        return merged_chunks[:top_k]

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
                page_start=(record.chunk_metadata or {}).get("page_start") or record.page,
                page_end=(record.chunk_metadata or {}).get("page_end") or record.page,
                heading_path=(record.chunk_metadata or {}).get("heading_path") or [],
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
        all_chunks = self._load_chunks()
        idf = self._build_idf(all_chunks, keywords)
        scored_chunks: list[tuple[float, RetrievedChunk]] = []

        for chunk in all_chunks:
            bm25_score = self._score_chunk_bm25(chunk=chunk, keywords=keywords, idf=idf)
            heuristic_score = self._score_chunk(
                chunk=chunk,
                phrases=phrases,
                keywords=keywords,
                preferred_sections=preferred_sections,
            )
            score = bm25_score + heuristic_score
            if score > 0:
                scored_chunks.append(
                    (
                        score,
                        chunk.model_copy(
                            update={
                                "score": float(score),
                                "score_components": {
                                    "keyword_bm25": round(bm25_score, 4),
                                    "keyword_heuristic": float(heuristic_score),
                                },
                            }
                        ),
                    )
                )

        scored_chunks.sort(
            key=lambda item: (
                self._matches_preferred_section(item[1], preferred_sections),
                item[0],
            ),
            reverse=True,
        )
        return [chunk for _, chunk in scored_chunks[:top_k]]

    def _fuse_candidates(
        self,
        vector_chunks: list[RetrievedChunk],
        keyword_chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        by_id: dict[str, RetrievedChunk] = {}
        scores: dict[str, dict[str, float]] = {}

        for rank, chunk in enumerate(vector_chunks, start=1):
            by_id.setdefault(chunk.chunk_id, chunk)
            scores.setdefault(chunk.chunk_id, {})["vector_rrf"] = 1 / (self.RRF_K + rank)

        for rank, chunk in enumerate(keyword_chunks, start=1):
            by_id.setdefault(chunk.chunk_id, chunk)
            keyword_rrf = 1 / (self.RRF_K + rank)
            scores.setdefault(chunk.chunk_id, {})["keyword_rrf"] = keyword_rrf
            if chunk.score is not None:
                scores[chunk.chunk_id]["keyword_score"] = chunk.score

        fused: list[RetrievedChunk] = []
        for chunk_id, chunk in by_id.items():
            components = scores.get(chunk_id, {})
            rrf_score = components.get("vector_rrf", 0.0) + components.get("keyword_rrf", 0.0)
            keyword_score = components.get("keyword_score", 0.0)
            final_score = (rrf_score * 100) + min(keyword_score, 20)
            fused.append(
                chunk.model_copy(
                    update={
                        "score": round(final_score, 4),
                        "score_components": {
                            **chunk.score_components,
                            **{key: round(value, 4) for key, value in components.items()},
                            "hybrid_rrf": round(rrf_score, 4),
                            "hybrid_score": round(final_score, 4),
                        },
                    }
                )
            )

        fused.sort(key=lambda chunk: chunk.score or 0, reverse=True)
        return fused[:top_k]

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

        if "pit lane speed" in normalized_question or "pit lane speeding" in normalized_question:
            phrases.append("pit lane speed")

        if "dangerous driving" in normalized_question:
            phrases.append("dangerous driving")

        if "track limits" in normalized_question:
            phrases.append("track limits")

        if "impeding" in normalized_question:
            phrases.append("impeding")

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
            "dangerous": ["dangerous", "danger", "endanger", "unsafe", "incident", "penalty"],
            "driving": ["driving", "driver", "incident", "penalty"],
            "release": ["release", "released", "pit"],
            "pit": ["pit", "lane", "entry", "exit", "speed", "limit"],
            "lane": ["lane", "pit", "speed", "limit"],
            "speed": ["speed", "speeding", "limit", "pit", "lane"],
            "speeding": ["speeding", "speed", "limit", "pit", "lane"],
            "limit": ["limit", "speed", "speeding", "pit", "lane"],
            "penalty": ["penalty", "penalties", "sanctions", "stewards", "investigation"],
            "stewards": ["stewards", "penalty", "investigation", "incident", "decision"],
            "investigation": ["investigation", "stewards", "incident", "penalty"],
            "incident": ["incident", "investigation", "stewards", "penalty"],
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

        for match in re.finditer(r"(?<![a-z])section\s*([a-f])(?![a-z])", normalized_question, flags=re.IGNORECASE):
            section = f"Section {match.group(1).upper()}"
            if section not in matched_sections:
                matched_sections.append(section)

        for section, keywords in self.SECTION_KEYWORDS.items():
            if any(keyword in normalized_question for keyword in keywords):
                matched_sections.append(section)

        return list(dict.fromkeys(matched_sections))

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
            if self._matches_preferred_section(chunk, preferred_sections)
        ]
        return filtered or chunks

    def _matches_preferred_section(self, chunk: RetrievedChunk, preferred_sections: list[str]) -> bool:
        if not preferred_sections:
            return False
        normalized_title = chunk.document_title.lower()
        normalized_section = self._chunk_section_code(chunk).lower()
        return any(
            section.lower() in normalized_title or section.lower() == normalized_section
            for section in preferred_sections
        )

    def _count_phrase_matches(self, chunk: RetrievedChunk, phrases: list[str]) -> int:
        normalized_content = chunk.content.lower()
        return sum(1 for phrase in phrases if phrase in normalized_content)

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

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _build_idf(self, chunks: list[RetrievedChunk], keywords: list[str]) -> dict[str, float]:
        if not chunks:
            return {}

        doc_count = len(chunks)
        idf: dict[str, float] = {}
        for keyword in keywords:
            if not keyword:
                continue
            matches = sum(1 for chunk in chunks if keyword in chunk.content.lower())
            idf[keyword] = math.log(1 + (doc_count - matches + 0.5) / (matches + 0.5)) if matches else 0.0
        return idf

    def _score_chunk_bm25(
        self,
        *,
        chunk: RetrievedChunk,
        keywords: list[str],
        idf: dict[str, float],
    ) -> float:
        tokens = self._tokenize(chunk.content)
        if not tokens:
            return 0.0

        token_counts: dict[str, int] = {}
        for token in tokens:
            token_counts[token] = token_counts.get(token, 0) + 1

        k1 = 1.5
        b = 0.75
        avgdl = 180
        doc_len = len(tokens)
        score = 0.0
        for keyword in keywords:
            normalized = keyword.lower()
            tf = token_counts.get(normalized, 0)
            if tf == 0 and " " in normalized and normalized in chunk.content.lower():
                tf = 1
            if tf == 0:
                continue
            denominator = tf + k1 * (1 - b + b * doc_len / avgdl)
            score += idf.get(normalized, 0.0) * ((tf * (k1 + 1)) / denominator)

        return round(score, 4)
