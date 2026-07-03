from app.schemas.pdf import PdfPage
from app.services.chunker import RegulationChunker


def test_chunker_extracts_document_metadata_and_article() -> None:
    chunker = RegulationChunker()
    pages = [
        PdfPage(
            page_number=7,
            text=(
                "B5.14 Unsafe release\n"
                "Cars must not be released from a pit stop position in a way that could endanger pit lane personnel.\n"
                "The stewards may impose a penalty."
            ),
        )
    ]

    chunks = chunker.chunk_document(
        document_title="FIA 2026 F1 Regulations - Section B [Sporting] - Iss 07 - 2026-06-25",
        pages=pages,
        max_chars=160,
        source_path="data/regulations/raw/section-b.pdf",
    )

    assert len(chunks) >= 1
    assert chunks[0].section_code == "Section B"
    assert chunks[0].article == "B5.14"
    assert chunks[0].page_number == 7
    assert chunks[0].page_start == 7
    assert chunks[0].page_end == 7
    assert chunks[0].heading_path == ["Section B", "B5.14"]
    assert chunks[0].chunk_index == 1
    assert chunks[0].source_path == "data/regulations/raw/section-b.pdf"
    assert chunks[0].chunk_id.startswith("fia-2026-f1-regulations-section-b-sporting")
    assert "Unsafe release" in chunks[0].content


def test_chunker_skips_index_like_pages() -> None:
    chunker = RegulationChunker()
    pages = [
        PdfPage(
            page_number=2,
            text=(
                "CONTENTS:\n"
                "ARTICLE 1 1\n"
                "ARTICLE 2 2\n"
                "ARTICLE 3 3\n"
            ),
        )
    ]

    assert chunker.chunk_document("FIA 2026 F1 Regulations - Section A", pages) == []
