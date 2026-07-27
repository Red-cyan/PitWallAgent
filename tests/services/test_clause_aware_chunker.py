from app.schemas.regulation_document import RegulationArticle, RegulationClause, RegulationDocument
from app.services.chunker import RegulationChunker


def _document(text: str) -> RegulationDocument:
    clause = RegulationClause(
        clause_id="B5.14.2", article_id="B5", article_title="Pit Lane",
        level=3, page_start=10, page_end=11, paragraphs=[text],
    )
    return RegulationDocument(
        document_key="fia-2026-section-b", document_title="FIA Regulations Section B",
        section_code="Section B", page_count=20,
        articles=[RegulationArticle(article_id="B5", title="Pit Lane", page_start=10, page_end=11, clauses=[clause])],
    )


def test_clause_chunk_ids_are_repeatable_and_embedding_text_has_breadcrumb() -> None:
    chunker = RegulationChunker()
    document = _document("Cars must not be released in an unsafe manner.")

    first = chunker.chunk_structure(document, corpus_version="v1")
    second = chunker.chunk_structure(document, corpus_version="v1")

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert first[0].article == "B5.14.2"
    assert first[0].clause_id == "B5.14.2"
    assert "Section B > B5 Pit Lane > B5.14.2" in (first[0].embedding_text or "")
    assert first[0].content.startswith("B5.14.2")


def test_long_clause_splits_on_semantic_boundaries_with_stable_parts() -> None:
    text = " ".join(["First requirement applies;" for _ in range(50)])
    chunks = [chunk for chunk in RegulationChunker().chunk_structure(_document(text), corpus_version="v1", max_chars=180)
              if chunk.chunk_type == "clause"]

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 180 for chunk in chunks)
    assert [chunk.part_ordinal for chunk in chunks] == list(range(1, len(chunks) + 1))
    assert all(chunk.content.endswith(";") for chunk in chunks[1:-1])
