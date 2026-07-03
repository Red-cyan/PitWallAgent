from app.repositories.rule_repository import RuleRepository
from app.schemas.rules import RetrievedChunk


def test_plank_question_prefers_technical_section() -> None:
    repository = RuleRepository()

    chunks = repository.search_relevant_chunks("What is the plank wear limit?")

    assert chunks
    assert "Section C" in chunks[0].document_title
    assert chunks[0].score is not None


def test_unsafe_release_question_prefers_sporting_section() -> None:
    repository = RuleRepository()

    chunks = repository.search_relevant_chunks("What is an unsafe release?")

    assert chunks
    assert "Section B" in chunks[0].document_title
    assert chunks[0].score is not None


def test_general_principles_question_prefers_general_section() -> None:
    repository = RuleRepository()

    chunks = repository.search_relevant_chunks("What are the general principles?")

    assert chunks
    assert "Section A" in chunks[0].document_title
    assert chunks[0].score is not None


def test_red_flag_question_in_chinese_prefers_sporting_section() -> None:
    class StubQueryRewriter:
        def rewrite(self, question: str) -> list[str]:
            return ["What is a red flag in Formula 1 regulations?"]

    repository = RuleRepository(query_rewriter=StubQueryRewriter())

    chunks = repository.search_relevant_chunks("红旗是什么？")

    assert chunks
    assert "Section B" in chunks[0].document_title
    assert chunks[0].score is not None


def test_red_flag_question_in_chinese_without_rewrite_still_prefers_sporting_section() -> None:
    class EmptyQueryRewriter:
        def rewrite(self, question: str) -> list[str]:
            return []

    repository = RuleRepository(query_rewriter=EmptyQueryRewriter())

    chunks = repository.search_relevant_chunks("\u7ea2\u65d7\u662f\u4ec0\u4e48\uff1f")

    assert chunks
    assert "Section B" in chunks[0].document_title


def test_chinese_pit_lane_speeding_question_expands_to_regulation_keywords() -> None:
    repository = RuleRepository()

    normalized = repository._normalize_question("维修区超速是什么")
    keywords = repository._expand_keywords(normalized)
    preferred_sections = repository._match_preferred_sections(normalized)

    assert "pit" in keywords
    assert "lane" in keywords
    assert "speed" in keywords
    assert "penalty" in keywords
    assert preferred_sections == ["Section B"]


def test_chinese_dangerous_driving_question_expands_to_regulation_keywords() -> None:
    repository = RuleRepository()

    normalized = repository._normalize_question("危险驾驶是什么")
    keywords = repository._expand_keywords(normalized)
    preferred_sections = repository._match_preferred_sections(normalized)

    assert "dangerous" in keywords
    assert "stewards" in keywords
    assert "penalty" in keywords
    assert preferred_sections == ["Section B"]


def test_compact_section_name_prefers_requested_section() -> None:
    class EmptyQueryRewriter:
        def rewrite(self, question: str) -> list[str]:
            return []

    repository = RuleRepository(query_rewriter=EmptyQueryRewriter())

    debug = repository.debug_retrieval("SectionA讲了什么内容", top_k=3)

    assert debug.normalized_question.startswith("Section A")
    assert debug.preferred_sections == ["Section A"]
    assert debug.retrieved_chunks
    assert all("Section A" in chunk.document_title for chunk in debug.retrieved_chunks)


def test_hybrid_fusion_keeps_vector_only_candidates_with_score_components() -> None:
    repository = RuleRepository()
    vector_chunk = RetrievedChunk(
        chunk_id="vector-only",
        content="A car must follow the race director instructions.",
        document_title="FIA 2026 F1 Regulations - Section B [Sporting]",
        article="ARTICLE 1",
        section="Section B",
        page=4,
    )
    keyword_chunk = RetrievedChunk(
        chunk_id="keyword-hit",
        content="The stewards may impose a penalty for a pit lane infringement.",
        score=9.0,
        document_title="FIA 2026 F1 Regulations - Section B [Sporting]",
        article="ARTICLE 2",
        section="Section B",
        page=5,
        score_components={"keyword_bm25": 1.5},
    )

    fused = repository._fuse_candidates([vector_chunk], [keyword_chunk], top_k=5)

    assert {chunk.chunk_id for chunk in fused} == {"vector-only", "keyword-hit"}
    vector_result = next(chunk for chunk in fused if chunk.chunk_id == "vector-only")
    assert vector_result.score is not None
    assert vector_result.score_components["vector_rrf"] > 0
    assert vector_result.score_components["hybrid_score"] > 0


def test_debug_retrieval_exposes_candidate_stages() -> None:
    class EmptyQueryRewriter:
        def rewrite(self, question: str) -> list[str]:
            return []

    repository = RuleRepository(query_rewriter=EmptyQueryRewriter())

    debug = repository.debug_retrieval("维修区超速是什么", top_k=2)

    assert debug.retrieval_queries
    assert debug.keyword_candidates
    assert debug.hybrid_candidates
    assert debug.retrieved_chunks
    assert debug.retrieved_chunks[0].score_components
