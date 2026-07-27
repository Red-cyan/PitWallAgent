from app.repositories.rule_repository import RuleRepository
from app.schemas.rules import RetrievedChunk


def test_rule_repository_does_not_return_arbitrary_chunk_when_rerank_has_no_signal() -> None:
    repository = RuleRepository()
    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        content="The competitor must submit financial reports by the deadline.",
        score=None,
        document_title="FIA 2026 F1 Regulations - Section D [Financial]",
        article="ARTICLE 10",
        section="Section D",
        page=12,
    )

    chunks = repository._rerank_chunks(
        chunks=[chunk],
        top_k=3,
        phrases=[],
        keywords=["safety", "car"],
        preferred_sections=["Section B"],
    )

    assert chunks == []


def test_rule_repository_keeps_chunks_with_enough_keyword_signal() -> None:
    repository = RuleRepository()
    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        content="The safety car may be deployed to neutralise a race.",
        score=None,
        document_title="FIA 2026 F1 Regulations - Section B [Sporting]",
        article="ARTICLE 55",
        section="Section B",
        page=41,
    )

    chunks = repository._rerank_chunks(
        chunks=[chunk],
        top_k=3,
        phrases=["safety car"],
        keywords=["safety", "car"],
        preferred_sections=["Section B"],
    )

    assert len(chunks) == 1
    assert chunks[0].score is not None
    assert chunks[0].score >= repository.MIN_RERANK_SCORE


def test_rule_repository_does_not_treat_section_match_as_evidence() -> None:
    repository = RuleRepository()
    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        content="Competitors must submit entry documents before the deadline.",
        score=None,
        document_title="FIA 2026 F1 Regulations - Section B [Sporting]",
        article="ARTICLE 1",
        section="Section B",
        page=2,
    )

    chunks = repository._rerank_chunks(
        chunks=[chunk],
        top_k=3,
        phrases=[],
        keywords=["safety", "car"],
        preferred_sections=["Section B"],
    )

    assert chunks == []


def test_adjacent_clause_parts_are_appended_without_changing_hit_rank() -> None:
    repository = RuleRepository(prefer_database=False)
    first = RetrievedChunk(chunk_id="part-1", content="first", document_title="Section B",
                           document_key="b", clause_id="B5.1", article="B5.1", part_ordinal=1)
    second = RetrievedChunk(chunk_id="part-2", content="second", document_title="Section B",
                            document_key="b", clause_id="B5.1", article="B5.1", part_ordinal=2)
    repository._cached_chunks = [first, second]

    expanded = repository.expand_clause_context([second])

    assert [chunk.chunk_id for chunk in expanded] == ["part-2", "part-1"]
