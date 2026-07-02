import json
from pathlib import Path

from app.schemas.chunk import RegulationChunk
from app.schemas.pdf import PdfPage
from app.services.regulation_ingestion_service import RegulationIngestionService


class StubReader:
    def read_pages(self, pdf_path: str | Path) -> list[PdfPage]:
        return [
            PdfPage(
                page_number=1,
                text=(
                    "ARTICLE 1 Scope\n"
                    "These regulations apply to the championship.\n"
                    "Additional paragraph for chunking."
                ),
            )
        ]


class StubEmbeddingService:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(index), float(len(text))] for index, text in enumerate(texts, start=1)]


class StubStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[RegulationChunk], list[list[float]] | None]] = []

    def replace_document_chunks(
        self,
        document_title: str,
        chunks: list[RegulationChunk],
        embeddings: list[list[float]] | None,
    ) -> None:
        self.calls.append((document_title, chunks, embeddings))


def test_regulation_ingestion_service_builds_manifest_and_persists_chunks(tmp_path: Path) -> None:
    pdf_path = tmp_path / "FIA 2026 F1 Regulations - Section A [General].pdf"
    pdf_path.write_text("placeholder", encoding="utf-8")
    output_path = tmp_path / "processed" / "chunks.json"
    store = StubStore()
    service = RegulationIngestionService(
        reader=StubReader(),
        embedding_service=StubEmbeddingService(),
        store=store,
    )

    summary = service.ingest_documents([pdf_path], output_path=output_path)

    assert summary.document_count == 1
    assert summary.chunk_count >= 1
    assert summary.embedded_chunk_count == summary.chunk_count
    assert output_path.exists()
    assert len(store.calls) == 1
    assert store.calls[0][0] == pdf_path.stem
    manifest = json.loads(output_path.read_text(encoding="utf-8"))
    assert manifest[0]["document_title"] == pdf_path.stem
    assert manifest[0]["section_code"] == "Section A"
    assert manifest[0]["article"] == "ARTICLE 1"


def test_regulation_ingestion_service_can_skip_embeddings_and_db(tmp_path: Path) -> None:
    pdf_path = tmp_path / "FIA 2026 F1 Regulations - Section C [Technical].pdf"
    pdf_path.write_text("placeholder", encoding="utf-8")
    service = RegulationIngestionService(reader=StubReader(), store=StubStore())

    summary = service.ingest_documents(
        [pdf_path],
        output_path=tmp_path / "chunks.json",
        persist_db=False,
        include_embeddings=False,
    )

    assert summary.document_count == 1
    assert summary.embedded_chunk_count == 0
