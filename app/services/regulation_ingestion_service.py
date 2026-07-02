import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import log_structured
from app.db.engine import SessionLocal
from app.db.models import RegulationChunkRecord
from app.rag.embedding.base import EmbeddingService
from app.rag.embedding.factory import build_embedding_service
from app.schemas.chunk import RegulationChunk
from app.schemas.rag import RegulationDocumentIngestionResult, RegulationIngestionSummary
from app.services.chunker import RegulationChunker
from app.services.pdf_reader import RegulationPdfReader


class RegulationChunkStore(Protocol):
    def replace_document_chunks(
        self,
        document_title: str,
        chunks: list[RegulationChunk],
        embeddings: list[list[float]] | None,
    ) -> None:
        """Replace persisted chunks for a single regulation document."""


class SqlAlchemyRegulationChunkStore:
    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def replace_document_chunks(
        self,
        document_title: str,
        chunks: list[RegulationChunk],
        embeddings: list[list[float]] | None,
    ) -> None:
        with self.session_factory() as session:
            existing_records = session.execute(
                select(RegulationChunkRecord).where(RegulationChunkRecord.document_title == document_title)
            ).scalars().all()
            existing_by_chunk_id = {record.chunk_id: record for record in existing_records}
            incoming_ids = {chunk.chunk_id for chunk in chunks}

            for record in existing_records:
                if record.chunk_id not in incoming_ids:
                    session.delete(record)

            for index, chunk in enumerate(chunks):
                record = existing_by_chunk_id.get(chunk.chunk_id)
                embedding = embeddings[index] if embeddings is not None else None
                metadata = {
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "source_path": chunk.source_path,
                }

                if record is None:
                    session.add(
                        RegulationChunkRecord(
                            chunk_id=chunk.chunk_id,
                            document_title=chunk.document_title,
                            section_code=chunk.section_code,
                            article=chunk.article,
                            page=chunk.page_number,
                            content=chunk.content,
                            embedding=embedding,
                            chunk_metadata=metadata,
                        )
                    )
                    continue

                record.document_title = chunk.document_title
                record.section_code = chunk.section_code
                record.article = chunk.article
                record.page = chunk.page_number
                record.content = chunk.content
                record.embedding = embedding
                record.chunk_metadata = metadata

            session.commit()


class RegulationIngestionService:
    def __init__(
        self,
        reader: RegulationPdfReader | None = None,
        chunker: RegulationChunker | None = None,
        embedding_service: EmbeddingService | None = None,
        store: RegulationChunkStore | None = None,
    ) -> None:
        self.reader = reader or RegulationPdfReader()
        self.chunker = chunker or RegulationChunker()
        self.embedding_service = embedding_service
        self.store = store or SqlAlchemyRegulationChunkStore()
        self.logger = logging.getLogger("pitwall.rag.ingestion")

    def discover_documents(self, raw_dir: str | Path = "data/regulations/raw") -> list[Path]:
        base_path = Path(raw_dir)
        return sorted(path for path in base_path.glob("*.pdf") if path.is_file())

    def ingest_corpus(
        self,
        raw_dir: str | Path = "data/regulations/raw",
        output_path: str | Path = "data/regulations/processed/chunks.json",
        *,
        persist_json: bool = True,
        persist_db: bool = True,
        include_embeddings: bool = True,
    ) -> RegulationIngestionSummary:
        return self.ingest_documents(
            self.discover_documents(raw_dir),
            output_path=output_path,
            persist_json=persist_json,
            persist_db=persist_db,
            include_embeddings=include_embeddings,
        )

    def ingest_documents(
        self,
        pdf_paths: Sequence[str | Path],
        output_path: str | Path = "data/regulations/processed/chunks.json",
        *,
        persist_json: bool = True,
        persist_db: bool = True,
        include_embeddings: bool = True,
    ) -> RegulationIngestionSummary:
        documents: list[RegulationDocumentIngestionResult] = []
        serialized_chunks: list[dict] = []
        total_embedded_chunks = 0

        for pdf_path in [Path(path) for path in pdf_paths]:
            pages = self.reader.read_pages(pdf_path)
            chunks = self.chunker.chunk_document(
                document_title=pdf_path.stem,
                pages=pages,
                source_path=str(pdf_path),
            )
            embeddings = self._embed_chunks(chunks) if include_embeddings else None

            if persist_db and chunks:
                self.store.replace_document_chunks(pdf_path.stem, chunks, embeddings)

            serialized_chunks.extend(chunk.model_dump(mode="json") for chunk in chunks)
            embedded_chunk_count = len(embeddings or [])
            total_embedded_chunks += embedded_chunk_count
            section_code = chunks[0].section_code if chunks else self.chunker._extract_section_code(pdf_path.stem)

            documents.append(
                RegulationDocumentIngestionResult(
                    document_title=pdf_path.stem,
                    source_path=str(pdf_path),
                    section_code=section_code,
                    page_count=len(pages),
                    chunk_count=len(chunks),
                    embedded_chunk_count=embedded_chunk_count,
                )
            )
            log_structured(
                self.logger,
                "regulation_document_ingested",
                document_title=pdf_path.stem,
                page_count=len(pages),
                chunk_count=len(chunks),
                embedded_chunk_count=embedded_chunk_count,
                persist_db=persist_db,
            )

        resolved_output_path = Path(output_path)
        if persist_json:
            resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_output_path.write_text(
                json.dumps(serialized_chunks, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        summary = RegulationIngestionSummary(
            document_count=len(documents),
            chunk_count=len(serialized_chunks),
            embedded_chunk_count=total_embedded_chunks,
            output_path=str(resolved_output_path) if persist_json else None,
            documents=documents,
        )
        log_structured(
            self.logger,
            "regulation_corpus_ingested",
            document_count=summary.document_count,
            chunk_count=summary.chunk_count,
            embedded_chunk_count=summary.embedded_chunk_count,
            persist_json=persist_json,
            persist_db=persist_db,
        )
        return summary

    def _embed_chunks(self, chunks: list[RegulationChunk]) -> list[list[float]]:
        if not chunks:
            return []

        embedding_service = self.embedding_service or build_embedding_service()
        embeddings = embedding_service.embed_texts([chunk.content for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError("Embedding service returned an unexpected number of vectors.")
        return embeddings
