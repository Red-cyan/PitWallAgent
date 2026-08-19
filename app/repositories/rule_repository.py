import json
import logging
import math
import re
from pathlib import Path
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.config.settings import settings
from app.db.engine import SessionLocal
from app.db.models import RegulationChunkRecord, RegulationCorpusRecord
from app.rag.retrieval.query_rewriter import QueryRewriter
from app.schemas.rules import ActiveCorpusResponse, RetrievalDebugResponse, RetrievedChunk

# 默认 chunks 文件基于项目根目录解析，而不是当前工作目录，
# 避免从任意目录启动 uvicorn 时 FileNotFoundError 导致 500。
_DEFAULT_CHUNKS_FILE = Path(__file__).resolve().parents[2] / "data" / "regulations" / "processed" / "chunks.json"


class RuleRepository:
    VECTOR_CANDIDATE_LIMIT = 40
    KEYWORD_CANDIDATE_LIMIT = 40
    HYBRID_CANDIDATE_LIMIT = 50
    MIN_RERANK_SCORE = 8
    PARTIAL_RERANK_SCORE = 1
    MIN_KEYWORD_EVIDENCE_SCORE = 6
    KEYWORD_GUARDRAIL_SCORE = 20
    RRF_K = 60
    QUERY_STOP_WORDS = {
        "about",
        "apply",
        "applies",
        "are",
        "does",
        "explain",
        "formula",
        "from",
        "govern",
        "governs",
        "how",
        "into",
        "regulation",
        "regulations",
        "the",
        "under",
        "what",
        "when",
        "which",
        "with",
    }
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
        "pit box": "designated pit stop position garage released unsafe release",
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
            "track limits",
            "track limit",
            "impeding",
            "impede",
            "sporting",
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
            "structure",
        ],
        "Section D": ["f1 team cost cap", "team cost cap"],
        "Section E": ["power unit manufacturer", "pu manufacturer", "manufacturer cost cap"],
        "Section F": ["operational", "wind tunnel"],
    }

    def __init__(
        self,
        query_rewriter: QueryRewriter | None = None,
        *,
        prefer_database: bool | None = None,
        chunks_file: str | Path | None = None,
        chunks_data: list[dict] | None = None,
    ) -> None:
        self.chunks_file = Path(chunks_file or _DEFAULT_CHUNKS_FILE)
        self._chunk_data = chunks_data
        self.prefer_database = (
            settings.regulation_prefer_database
            if prefer_database is None
            else prefer_database
        )
        self._cached_chunks: list[RetrievedChunk] | None = None
        self._cached_chunks_version: str | None = None
        self._normalized_content_cache: dict[str, str] = {}
        self._token_stats_cache: dict[str, tuple[dict[str, int], int]] = {}
        self._document_frequency_cache: dict[str, int] = {}
        self._token_chunk_ids: dict[str, set[str]] | None = None
        self._chunks_by_id: dict[str, RetrievedChunk] = {}
        self.query_rewriter = query_rewriter or QueryRewriter()

    def search_relevant_chunks(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
        debug_data = self.debug_retrieval(question=question, top_k=top_k)
        return self.expand_clause_context(debug_data.retrieved_chunks)

    def expand_clause_context(self, hits: list[RetrievedChunk], max_neighbors: int = 1) -> list[RetrievedChunk]:
        """Insert adjacent parts next to their hit without changing hit rank or score.

        Neighbors are kept immediately after the hit so downstream context
        assembly cannot drop a referenced sub-clause (for example VSC clause
        ``c`` referencing the requirements of ``b``) before a budget cut.
        """
        if not hits or max_neighbors < 1:
            return hits
        all_chunks = self._load_chunks()
        hit_ids = {chunk.chunk_id for chunk in hits}
        selected_ids = set(hit_ids)
        expanded: list[RetrievedChunk] = []
        for hit in hits:
            expanded.append(hit)
            if not hit.clause_id:
                continue
            neighbors = [
                chunk for chunk in all_chunks
                if chunk.chunk_id not in hit_ids
                and chunk.chunk_id not in selected_ids
                and chunk.document_key == hit.document_key
                and chunk.clause_id == hit.clause_id
                and chunk.chunk_type == hit.chunk_type
                and abs(chunk.part_ordinal - hit.part_ordinal) == 1
            ]
            neighbors.sort(key=lambda chunk: (abs(chunk.part_ordinal - hit.part_ordinal), chunk.part_ordinal))
            for neighbor in neighbors[:max_neighbors]:
                expanded.append(neighbor)
                selected_ids.add(neighbor.chunk_id)
        return expanded

    def search_keywords(self, question: str, top_k: int = 5) -> list[RetrievedChunk]:
        """Run the deterministic keyword pipeline without an LLM or embedding model."""

        normalized_question = self._normalize_question(question)
        phrases = self._extract_phrases(normalized_question)
        keywords = self._expand_keywords(normalized_question)
        preferred_sections = self._match_preferred_sections(normalized_question)
        exact_clause_ids = self._extract_exact_clause_ids(normalized_question)
        candidates = self._search_by_keywords(
            phrases=phrases,
            keywords=keywords,
            preferred_sections=preferred_sections,
            exact_clause_ids=exact_clause_ids,
            top_k=self.KEYWORD_CANDIDATE_LIMIT,
        )
        return self._rerank_chunks(
            chunks=candidates,
            top_k=top_k,
            phrases=phrases,
            keywords=keywords,
            preferred_sections=preferred_sections,
            exact_clause_ids=exact_clause_ids,
        )

    def search(
        self,
        question: str,
        *,
        mode: Literal["keyword", "vector", "hybrid"] = "hybrid",
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Run one retrieval strategy through a stable evaluation-facing API."""

        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        if mode == "keyword":
            return self.search_keywords(question, top_k=top_k)

        normalized_question = self._normalize_question(question)
        rewritten_queries = self.query_rewriter.rewrite(question)
        questions = self._deduplicate_queries([normalized_question, *rewritten_queries])
        if mode == "vector":
            scoring_question = " ".join(questions)
            candidate_pool = self._search_by_vector_queries(
                questions,
                top_k=max(top_k, settings.regulation_rerank_max_candidates),
                preferred_sections=self._match_preferred_sections(normalized_question),
            )
            vector_results = self._apply_model_rerank(
                question=scoring_question,
                chunks=candidate_pool,
                top_k=top_k,
            )
            return self._boost_exact_vector_results(
                vector_results,
                self._extract_exact_clause_ids(normalized_question),
                top_k,
            )
        if mode == "hybrid":
            return self.debug_retrieval(question, top_k=top_k).retrieved_chunks
        raise ValueError(f"Unsupported retrieval mode: {mode}")

    def get_active_corpus(self) -> ActiveCorpusResponse | None:
        try:
            with SessionLocal() as session:
                row = session.execute(
                    select(
                        RegulationCorpusRecord,
                        func.count(RegulationChunkRecord.id),
                        func.count(RegulationChunkRecord.embedding),
                    )
                    .join(
                        RegulationChunkRecord,
                        RegulationChunkRecord.corpus_version == RegulationCorpusRecord.corpus_version,
                        isouter=True,
                    )
                    .where(RegulationCorpusRecord.active.is_(True))
                    .group_by(RegulationCorpusRecord.corpus_version)
                ).one_or_none()
        except SQLAlchemyError:
            return None
        if row is None:
            return None
        corpus, chunk_count, embedding_count = row
        return ActiveCorpusResponse(
            corpus_version=corpus.corpus_version,
            parser_version=corpus.parser_version,
            embedding_model=corpus.embedding_model,
            status=corpus.status,
            chunk_count=chunk_count,
            embedding_count=embedding_count,
            created_at=corpus.created_at.isoformat(),
            validation=corpus.validation or {},
        )

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
        exact_clause_ids = self._extract_exact_clause_ids(scoring_question)
        chunks = self._retrieve_candidate_chunks(
            retrieval_questions,
            top_k=top_k,
            phrases=phrases,
            keywords=keywords,
            preferred_sections=preferred_sections,
            exact_clause_ids=exact_clause_ids,
        )
        vector_candidates = chunks["vector"]
        keyword_candidates = chunks["keyword"]
        hybrid_candidates = chunks["hybrid"]
        hybrid_results = self._rerank_chunks(
            chunks=hybrid_candidates,
            top_k=max(top_k, settings.regulation_rerank_max_candidates),
            phrases=phrases,
            keywords=keywords,
            preferred_sections=preferred_sections,
            exact_clause_ids=exact_clause_ids,
        )
        keyword_results = self._rerank_chunks(
            chunks=keyword_candidates,
            top_k=top_k,
            phrases=phrases,
            keywords=keywords,
            preferred_sections=preferred_sections,
            exact_clause_ids=exact_clause_ids,
        )
        guardrail_results = self._apply_keyword_guardrail(hybrid_results, keyword_results)
        final_results = self._apply_model_rerank(
            question=scoring_question,
            chunks=guardrail_results,
            top_k=top_k,
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
            retrieved_chunks=final_results,
        )

    def _apply_keyword_guardrail(
        self,
        hybrid_results: list[RetrievedChunk],
        keyword_results: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        if not keyword_results or (keyword_results[0].score or 0.0) < self.KEYWORD_GUARDRAIL_SCORE:
            return hybrid_results
        return [
            chunk.model_copy(
                update={
                    "score_components": {
                        **chunk.score_components,
                        "keyword_guardrail": 1.0,
                    }
                }
            )
            for chunk in keyword_results
        ]

    def _apply_model_rerank(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        top_k: int,
        max_candidates: int | None = None,
    ) -> list[RetrievedChunk]:
        """使用交叉编码器重排候选，作为最终排序。

        模型不可用（未开启 / 加载失败）时原样返回；重排只改变顺序并补充
        rerank_model 分数，保留既有启发式 score_components 供证据强度判定。
        """
        if not chunks or top_k < 1:
            return chunks

        limit = max_candidates if max_candidates is not None else settings.regulation_rerank_max_candidates
        candidates = chunks[:limit]
        try:
            from app.rag.rerank.factory import build_reranker

            reranker = build_reranker()
        except Exception:
            reranker = None
        if reranker is None:
            return chunks[:top_k]

        texts = [chunk.content for chunk in candidates]
        model_scores = reranker.score(question, texts)

        scored: list[RetrievedChunk] = []
        for chunk, model_score in zip(candidates, model_scores, strict=True):
            scored.append(
                chunk.model_copy(
                    update={
                        "score": float(model_score),
                        "score_components": {
                            **chunk.score_components,
                            "rerank_heuristic": float(chunk.score or 0.0),
                            "rerank_model": float(model_score),
                        },
                    }
                )
            )

        scored.sort(key=lambda chunk: chunk.score or 0.0, reverse=True)
        return scored[:top_k]

    def _rerank_chunks(
        self,
        chunks: list[RetrievedChunk],
        top_k: int,
        phrases: list[str],
        keywords: list[str],
        preferred_sections: list[str],
        exact_clause_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        scored_chunks: list[tuple[float, RetrievedChunk]] = []

        for chunk in chunks:
            score = self._score_chunk(
                chunk=chunk,
                phrases=phrases,
                keywords=keywords,
                preferred_sections=preferred_sections,
            )
            if exact_clause_ids and (chunk.clause_id or chunk.article) in exact_clause_ids:
                score += 30
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
        exact_clause_ids: list[str] | None = None,
    ) -> dict[str, list[RetrievedChunk]]:
        vector_chunks = self._search_by_vector_queries(
            questions,
            top_k=max(top_k, self.VECTOR_CANDIDATE_LIMIT),
            preferred_sections=preferred_sections,
        )
        vector_chunks = self._boost_exact_vector_results(
            vector_chunks,
            exact_clause_ids or [],
            max(top_k, self.VECTOR_CANDIDATE_LIMIT),
        )
        keyword_chunks = self._search_by_keywords(
            phrases=phrases,
            keywords=keywords,
            preferred_sections=preferred_sections,
            exact_clause_ids=exact_clause_ids,
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

    def _boost_exact_vector_results(
        self,
        vector_chunks: list[RetrievedChunk],
        exact_clause_ids: list[str],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if not exact_clause_ids:
            return vector_chunks[:top_k]
        exact = [
            chunk.model_copy(
                update={
                    "score": max(chunk.score or 0.0, 100.0),
                    "score_components": {**chunk.score_components, "exact_clause": 1.0},
                }
            )
            for chunk in self._load_chunks()
            if (chunk.clause_id or chunk.article) in exact_clause_ids
        ]
        deduplicated = {chunk.chunk_id: chunk for chunk in [*exact, *vector_chunks]}
        return list(deduplicated.values())[:top_k]

    def _load_chunks(self) -> list[RetrievedChunk]:
        if self._cached_chunks is not None:
            # 缓存版本尚未跟踪（外部注入）时直接信任；否则仅在激活语料
            # 版本确认变化时重载，避免 ingest+activate 后检索仍用旧快照。
            if self._cached_chunks_version is None:
                return self._cached_chunks
            version = self._current_chunks_version()
            if version is None or version == self._cached_chunks_version:
                return self._cached_chunks

        if self.prefer_database:
            chunks = self._load_chunks_from_database()
            if chunks:
                self._cached_chunks = chunks
                self._cached_chunks_version = self._current_chunks_version()
                return self._cached_chunks

        self._cached_chunks = self._load_chunks_from_file()
        self._cached_chunks_version = "file"
        return self._cached_chunks

    def _current_chunks_version(self) -> str | None:
        """当前激活语料版本；无法确定（如 DB 不可用）返回 None。

        版本变化时自动重载 chunk 快照，使 ingest+activate 新语料后
        关键词/融合检索立即生效，而不必等到进程重启。
        """
        if not self.prefer_database:
            return "file"
        try:
            with SessionLocal() as session:
                return session.scalar(
                    select(RegulationCorpusRecord.corpus_version)
                    .where(RegulationCorpusRecord.active.is_(True))
                    .limit(1)
                )
        except SQLAlchemyError:
            return None

    def _load_chunks_from_database(self) -> list[RetrievedChunk]:
        try:
            with SessionLocal() as session:
                records = session.execute(
                    select(RegulationChunkRecord)
                    .join(RegulationCorpusRecord, RegulationCorpusRecord.corpus_version == RegulationChunkRecord.corpus_version)
                    .where(RegulationCorpusRecord.active.is_(True))
                    .order_by(RegulationChunkRecord.id)
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
                clause_id=record.clause_id or record.article,
                article_title=record.article_title,
                chunk_type=record.chunk_type,
                corpus_version=record.corpus_version,
                document_key=record.document_key,
                breadcrumb=(record.chunk_metadata or {}).get("heading_path") or [],
                part_ordinal=(record.chunk_metadata or {}).get("part_ordinal") or 1,
            )
            for record in records
        ]

    def _load_chunks_from_file(self) -> list[RetrievedChunk]:
        if self._chunk_data is not None:
            chunk_data = self._chunk_data
        else:
            try:
                with self.chunks_file.open("r", encoding="utf-8") as file:
                    chunk_data = json.load(file)
            except (FileNotFoundError, json.JSONDecodeError) as exc:
                logger = logging.getLogger("pitwall.rule_repository")
                logger.warning(
                    "chunks file unavailable; falling back to empty corpus",
                    extra={"error_type": exc.__class__.__name__, "path": str(self.chunks_file)},
                )
                return []

        return [
            RetrievedChunk(
                **{
                    **item,
                    "page": item.get("page") or item.get("page_number"),
                    "section": item.get("section") or item.get("section_code"),
                    "clause_id": item.get("clause_id") or item.get("article"),
                    "breadcrumb": item.get("breadcrumb") or item.get("heading_path") or [],
                }
            )
            for item in chunk_data
        ]

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

    def _search_by_vector_queries(
        self,
        questions: list[str],
        top_k: int,
        preferred_sections: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        merged_chunks: list[RetrievedChunk] = []
        seen_chunk_ids: set[str] = set()

        for question in questions:
            for chunk in self._search_by_vector(
                question,
                top_k=max(top_k, self.VECTOR_CANDIDATE_LIMIT),
                preferred_sections=preferred_sections,
            ):
                if chunk.chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk.chunk_id)
                merged_chunks.append(chunk)

        merged_chunks.sort(
            key=lambda chunk: (
                0
                if not preferred_sections or self._matches_preferred_section(chunk, preferred_sections)
                else 1,
                -(chunk.score or 0),
            )
        )
        return merged_chunks[:top_k]

    def _search_by_vector(
        self,
        question: str,
        top_k: int,
        preferred_sections: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        if not settings.regulation_vector_retrieval_enabled:
            return []
        if not self._has_vector_data():
            return []

        try:
            from app.rag.embedding.factory import build_embedding_service

            embedding_service = build_embedding_service()
            question_embedding = embedding_service.embed_query(question)
        except Exception:
            return []

        pool_size = max(top_k * 8, self.VECTOR_CANDIDATE_LIMIT * 2)
        try:
            with SessionLocal() as session:
                distance = RegulationChunkRecord.embedding.cosine_distance(question_embedding).label("distance")
                rows = session.execute(
                    select(RegulationChunkRecord, distance)
                    .join(RegulationCorpusRecord, RegulationCorpusRecord.corpus_version == RegulationChunkRecord.corpus_version)
                    .where(RegulationChunkRecord.embedding.is_not(None))
                    .where(RegulationCorpusRecord.active.is_(True))
                    .order_by(distance)
                    .limit(pool_size)
                ).all()
        except SQLAlchemyError:
            return []

        chunks: list[RetrievedChunk] = []
        for record, distance in rows:
            similarity = max(1.0 - float(distance), 0.0)
            chunks.append(
                self._chunk_from_record(
                    record,
                    score=similarity,
                    score_components={"vector_cosine": round(similarity, 4)},
                )
            )

        if preferred_sections:
            chunks.sort(
                key=lambda chunk: (
                    0 if self._matches_preferred_section(chunk, preferred_sections) else 1,
                    -(chunk.score or 0),
                )
            )
        return chunks[:top_k]

    def _chunk_from_record(
        self,
        record,
        *,
        score: float | None = None,
        score_components: dict[str, float] | None = None,
    ) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=record.chunk_id,
            content=record.content,
            score=score,
            document_title=record.document_title,
            article=record.article,
            section=record.section_code,
            page=record.page,
            page_start=(record.chunk_metadata or {}).get("page_start") or record.page,
            page_end=(record.chunk_metadata or {}).get("page_end") or record.page,
            heading_path=(record.chunk_metadata or {}).get("heading_path") or [],
            clause_id=record.clause_id or record.article,
            article_title=record.article_title,
            chunk_type=record.chunk_type,
            corpus_version=record.corpus_version,
            document_key=record.document_key,
            breadcrumb=(record.chunk_metadata or {}).get("heading_path") or [],
            part_ordinal=(record.chunk_metadata or {}).get("part_ordinal") or 1,
            score_components=score_components or {},
        )

    def _has_vector_data(self) -> bool:
        try:
            with SessionLocal() as session:
                chunk_id = session.scalar(
                    select(RegulationChunkRecord.id)
                    .join(RegulationCorpusRecord, RegulationCorpusRecord.corpus_version == RegulationChunkRecord.corpus_version)
                    .where(RegulationChunkRecord.embedding.is_not(None))
                    .where(RegulationCorpusRecord.active.is_(True))
                    .limit(1)
                )
        except SQLAlchemyError:
            return False
        return chunk_id is not None

    def _search_by_keywords(
        self,
        phrases: list[str],
        keywords: list[str],
        preferred_sections: list[str],
        top_k: int,
        exact_clause_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        all_chunks = self._load_chunks()
        candidate_chunks = self._keyword_candidates(all_chunks, [*keywords, *phrases])
        if exact_clause_ids:
            exact_chunks = [chunk for chunk in all_chunks if (chunk.clause_id or chunk.article) in exact_clause_ids]
            candidate_chunks = list({chunk.chunk_id: chunk for chunk in [*candidate_chunks, *exact_chunks]}.values())
        idf = self._build_idf(all_chunks, keywords)
        scored_chunks: list[tuple[float, RetrievedChunk]] = []

        for chunk in candidate_chunks:
            bm25_score = self._score_chunk_bm25(chunk=chunk, keywords=keywords, idf=idf)
            heuristic_score = self._score_chunk(
                chunk=chunk,
                phrases=phrases,
                keywords=keywords,
                preferred_sections=preferred_sections,
            )
            score = bm25_score + heuristic_score
            if exact_clause_ids and (chunk.clause_id or chunk.article) in exact_clause_ids:
                score += 30
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

        if "safety structure" in normalized_question:
            phrases.append("safety structure")

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

        if "fuel flow" in normalized_question or "flow meter" in normalized_question:
            phrases.append("fuel flow meter")

        return phrases

    def _expand_keywords(self, question: str) -> list[str]:
        raw_tokens = [
            token.strip(".,?!:;()[]").lower()
            for token in question.split()
            if len(token.strip(".,?!:;()[]")) >= 3
            and token.strip(".,?!:;()[]").lower() not in self.QUERY_STOP_WORDS
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
            "track": ["track", "leave", "leaving"],
            "limits": ["limit", "leave", "leaving"],
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

        for clause_id in self._extract_exact_clause_ids(question):
            matched_sections.append(f"Section {clause_id[0]}")

        for section, keywords in self.SECTION_KEYWORDS.items():
            if any(keyword in normalized_question for keyword in keywords):
                matched_sections.append(section)

        if "championship points" in normalized_question or "points awarded" in normalized_question:
            return ["Section A"]
        if "investigation" in normalized_question and any(term in normalized_question for term in ("appeal", "confidential")):
            return ["Section A"]

        return list(dict.fromkeys(matched_sections))

    def _extract_exact_clause_ids(self, question: str) -> list[str]:
        return list(dict.fromkeys(match.group(0).upper() for match in re.finditer(r"\b[A-F]\d+(?:\.\d+)+\b", question, re.I)))

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
        normalized_content = self._normalized_content(chunk)
        return sum(1 for phrase in phrases if phrase in normalized_content)

    def _score_chunk(
        self,
        chunk: RetrievedChunk,
        phrases: list[str],
        keywords: list[str],
        preferred_sections: list[str],
    ) -> int:
        normalized_content = self._normalized_content(chunk)
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
        if chunk.chunk_type == "article_overview":
            score = max(1, score - 4)
        for section in preferred_sections:
            if section.lower() == self._chunk_section_code(chunk).lower():
                score += 8

        return score

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _build_idf(self, chunks: list[RetrievedChunk], keywords: list[str]) -> dict[str, float]:
        if not chunks:
            return {}

        doc_count = len(chunks)
        self._ensure_token_index(chunks)
        idf: dict[str, float] = {}
        for keyword in keywords:
            if not keyword:
                continue
            matches = self._document_frequency_cache.get(keyword)
            if matches is None:
                matches = sum(1 for chunk in chunks if keyword in self._normalized_content(chunk))
                self._document_frequency_cache[keyword] = matches
            idf[keyword] = math.log(1 + (doc_count - matches + 0.5) / (matches + 0.5)) if matches else 0.0
        return idf

    def _score_chunk_bm25(
        self,
        *,
        chunk: RetrievedChunk,
        keywords: list[str],
        idf: dict[str, float],
    ) -> float:
        token_counts, doc_len = self._token_stats(chunk)
        if doc_len == 0:
            return 0.0

        k1 = 1.5
        b = 0.75
        avgdl = 180
        score = 0.0
        for keyword in keywords:
            normalized = keyword.lower()
            tf = token_counts.get(normalized, 0)
            if tf == 0 and " " in normalized and normalized in self._normalized_content(chunk):
                tf = 1
            if tf == 0:
                continue
            denominator = tf + k1 * (1 - b + b * doc_len / avgdl)
            score += idf.get(normalized, 0.0) * ((tf * (k1 + 1)) / denominator)

        return round(score, 4)

    def _normalized_content(self, chunk: RetrievedChunk) -> str:
        cached = self._normalized_content_cache.get(chunk.chunk_id)
        if cached is None:
            cached = chunk.content.lower()
            self._normalized_content_cache[chunk.chunk_id] = cached
        return cached

    def _token_stats(self, chunk: RetrievedChunk) -> tuple[dict[str, int], int]:
        cached = self._token_stats_cache.get(chunk.chunk_id)
        if cached is not None:
            return cached

        tokens = self._tokenize(chunk.content)
        token_counts: dict[str, int] = {}
        for token in tokens:
            token_counts[token] = token_counts.get(token, 0) + 1
        result = (token_counts, len(tokens))
        self._token_stats_cache[chunk.chunk_id] = result
        return result

    def _ensure_token_index(self, chunks: list[RetrievedChunk]) -> None:
        if self._token_chunk_ids is not None:
            return

        token_chunk_ids: dict[str, set[str]] = {}
        for chunk in chunks:
            self._chunks_by_id[chunk.chunk_id] = chunk
            token_counts, _ = self._token_stats(chunk)
            for token in token_counts:
                token_chunk_ids.setdefault(token, set()).add(chunk.chunk_id)
        self._token_chunk_ids = token_chunk_ids
        self._document_frequency_cache.update(
            {token: len(chunk_ids) for token, chunk_ids in token_chunk_ids.items()}
        )

    def _keyword_candidates(
        self,
        chunks: list[RetrievedChunk],
        terms: list[str],
    ) -> list[RetrievedChunk]:
        self._ensure_token_index(chunks)
        token_chunk_ids = self._token_chunk_ids or {}
        candidate_ids: set[str] = set()
        phrase_terms: list[str] = []
        for term in terms:
            normalized = term.lower().strip()
            if not normalized:
                continue
            if " " in normalized:
                phrase_terms.append(normalized)
            else:
                candidate_ids.update(token_chunk_ids.get(normalized, set()))

        if phrase_terms:
            for chunk in chunks:
                content = self._normalized_content(chunk)
                if any(phrase in content for phrase in phrase_terms):
                    candidate_ids.add(chunk.chunk_id)

        return [chunk for chunk in chunks if chunk.chunk_id in candidate_ids]
