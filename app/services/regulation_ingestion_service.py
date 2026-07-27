from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.logging import log_structured
from app.db.engine import SessionLocal
from app.db.models import RegulationChunkRecord, RegulationCorpusRecord
from app.rag.embedding.base import EmbeddingService
from app.rag.embedding.factory import build_embedding_service
from app.schemas.chunk import RegulationChunk
from app.schemas.rag import RegulationDocumentIngestionResult, RegulationIngestionSummary
from app.schemas.regulation_document import CorpusManifest, CorpusValidation, RegulationDocument
from app.services.chunker import RegulationChunker
from app.services.pdf_reader import RegulationPdfReader
from app.services.regulation_parser import RegulationStructureParser


class RegulationChunkStore(Protocol):
    def replace_document_chunks(self, document_title: str, chunks: list[RegulationChunk], embeddings: list[list[float]] | None) -> None: ...


class SqlAlchemyRegulationChunkStore:
    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def stage_corpus(
        self,
        manifest: CorpusManifest,
        chunks: list[RegulationChunk],
        embeddings: list[list[float]] | None,
        *,
        activate: bool,
    ) -> None:
        if activate and (manifest.validation is None or not manifest.validation.valid):
            raise ValueError("Cannot activate a corpus that has not passed validation.")
        with self.session_factory.begin() as session:  # type: ignore[attr-defined]
            session.execute(delete(RegulationChunkRecord).where(RegulationChunkRecord.corpus_version == manifest.corpus_version))
            session.execute(delete(RegulationCorpusRecord).where(RegulationCorpusRecord.corpus_version == manifest.corpus_version))
            if activate:
                session.execute(update(RegulationCorpusRecord).values(active=False).where(RegulationCorpusRecord.active.is_(True)))
            session.add(RegulationCorpusRecord(
                corpus_version=manifest.corpus_version,
                parser_version=manifest.parser_version,
                source_hashes=manifest.source_hashes,
                build_parameters={"chunk_max_chars": manifest.chunk_max_chars},
                embedding_model=manifest.embedding_model,
                status="active" if activate else manifest.status,
                active=activate,
                validation=manifest.validation.model_dump(mode="json") if manifest.validation else None,
            ))
            for index, chunk in enumerate(chunks):
                session.add(self._record(chunk, embeddings[index] if embeddings is not None else None))

    def replace_document_chunks(self, document_title: str, chunks: list[RegulationChunk], embeddings: list[list[float]] | None) -> None:
        with self.session_factory() as session:
            session.execute(delete(RegulationChunkRecord).where(RegulationChunkRecord.document_title == document_title))
            for index, chunk in enumerate(chunks):
                session.add(self._record(chunk, embeddings[index] if embeddings is not None else None))
            session.commit()

    def activate_corpus(self, corpus_version: str) -> None:
        with self.session_factory.begin() as session:  # type: ignore[attr-defined]
            corpus = session.get(RegulationCorpusRecord, corpus_version)
            if corpus is None or corpus.status not in {"validated", "active"}:
                raise ValueError(f"Corpus {corpus_version!r} is not validated.")
            session.execute(update(RegulationCorpusRecord).values(active=False, status="validated").where(RegulationCorpusRecord.active.is_(True)))
            corpus.active = True
            corpus.status = "active"

    def delete_corpus(self, corpus_version: str) -> None:
        with self.session_factory.begin() as session:  # type: ignore[attr-defined]
            corpus = session.get(RegulationCorpusRecord, corpus_version)
            if corpus is not None and corpus.active:
                raise ValueError("The active corpus cannot be deleted.")
            session.execute(delete(RegulationChunkRecord).where(RegulationChunkRecord.corpus_version == corpus_version))
            session.execute(delete(RegulationCorpusRecord).where(RegulationCorpusRecord.corpus_version == corpus_version))

    def _record(self, chunk: RegulationChunk, embedding: list[float] | None) -> RegulationChunkRecord:
        return RegulationChunkRecord(
            chunk_id=chunk.chunk_id, document_title=chunk.document_title, section_code=chunk.section_code,
            article=chunk.article, page=chunk.page_number, content=chunk.content, embedding=embedding,
            corpus_version=chunk.corpus_version, document_key=chunk.document_key,
            article_title=chunk.article_title, clause_id=chunk.clause_id, chunk_type=chunk.chunk_type,
            content_hash=chunk.content_hash, embedding_text=chunk.embedding_text,
            chunk_metadata={"page_start": chunk.page_start, "page_end": chunk.page_end,
                            "heading_path": chunk.heading_path, "part_ordinal": chunk.part_ordinal,
                            "source_path": chunk.source_path},
        )


class RegulationIngestionService:
    def __init__(self, reader: RegulationPdfReader | None = None, chunker: RegulationChunker | None = None,
                 embedding_service: EmbeddingService | None = None, store: RegulationChunkStore | None = None,
                 parser: RegulationStructureParser | None = None) -> None:
        self.reader = reader or RegulationPdfReader()
        self.parser = parser or RegulationStructureParser()
        self.chunker = chunker or RegulationChunker(self.parser)
        self.embedding_service = embedding_service
        self.store = store or SqlAlchemyRegulationChunkStore()
        self.logger = logging.getLogger("pitwall.rag.ingestion")

    def discover_documents(self, raw_dir: str | Path = "data/regulations/raw") -> list[Path]:
        return sorted(path for path in Path(raw_dir).glob("*.pdf") if path.is_file())

    def ingest_corpus(self, raw_dir: str | Path = "data/regulations/raw",
                      output_path: str | Path = "data/regulations/processed/chunks.json", **kwargs: Any) -> RegulationIngestionSummary:
        return self.ingest_documents(self.discover_documents(raw_dir), output_path=output_path, **kwargs)

    def ingest_documents(
        self, pdf_paths: Sequence[str | Path], output_path: str | Path = "data/regulations/processed/chunks.json", *,
        persist_json: bool = True, persist_db: bool = True, include_embeddings: bool = True,
        corpus_version: str | None = None, validate_only: bool = False, emit_markdown: bool = False,
        activate: bool = False, max_chars: int = 1600,
    ) -> RegulationIngestionSummary:
        paths = [Path(path) for path in pdf_paths]
        source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        version = corpus_version or f"build-{hashlib.sha256(''.join(source_hashes.values()).encode()).hexdigest()[:12]}"
        documents: list[RegulationDocument] = []
        all_chunks: list[RegulationChunk] = []
        results: list[RegulationDocumentIngestionResult] = []

        for path in paths:
            pages = self.reader.read_pages(path)
            try:
                document = self.parser.parse(path.stem, pages, path)
                chunks = self.chunker.chunk_structure(document, corpus_version=version, max_chars=max_chars)
                if not chunks:
                    chunks = self.chunker.chunk_document(path.stem, pages, max_chars, path, version)
            except ValueError:
                document = RegulationDocument(document_key=self.parser.document_key(path.stem), document_title=path.stem,
                                              section_code=self.chunker._extract_section_code(path.stem) or "Unknown",
                                              source_path=str(path), page_count=len(pages))
                chunks = self.chunker.chunk_document(path.stem, pages, max_chars, path, version)
            documents.append(document)
            all_chunks.extend(chunks)
            results.append(RegulationDocumentIngestionResult(document_title=path.stem, source_path=str(path),
                           section_code=document.section_code, page_count=len(pages), chunk_count=len(chunks),
                           embedded_chunk_count=0))

        validation = self._validate(documents, all_chunks)
        embeddings = self._embed_chunks(all_chunks) if include_embeddings and validation.valid and not validate_only else None
        for result in results:
            if embeddings is not None:
                result.embedded_chunk_count = result.chunk_count
        manifest = CorpusManifest(corpus_version=version, parser_version=self.parser.VERSION,
                                  source_hashes=source_hashes, chunk_max_chars=max_chars,
                                  embedding_model=settings.regulation_embedding_model if include_embeddings else None,
                                  status="validated" if validation.valid else "failed", validation=validation)
        if activate and not validation.valid:
            raise ValueError("Corpus validation failed; activation is forbidden: " + "; ".join(validation.errors))

        resolved_output = Path(output_path)
        if persist_db and not validate_only:
            stage_corpus = getattr(self.store, "stage_corpus", None)
            if callable(stage_corpus):
                stage_corpus(manifest, all_chunks, embeddings, activate=activate)
            else:
                by_document = {result.document_title: [] for result in results}
                for chunk in all_chunks:
                    by_document[chunk.document_title].append(chunk)
                offset = 0
                for title, chunks in by_document.items():
                    chunk_embeddings = embeddings[offset:offset + len(chunks)] if embeddings is not None else None
                    self.store.replace_document_chunks(title, chunks, chunk_embeddings)
                    offset += len(chunks)
        if activate and validation.valid and persist_db and not validate_only:
            manifest.status = "active"
            manifest.active = True
        if persist_json:
            self._write_artifacts(resolved_output, documents, all_chunks, manifest, emit_markdown)

        summary = RegulationIngestionSummary(document_count=len(results), chunk_count=len(all_chunks),
                    embedded_chunk_count=len(embeddings or []), output_path=str(resolved_output) if persist_json else None,
                    documents=results, corpus_version=version,
                    manifest_path=str(resolved_output.with_name("corpus_manifest.json")) if persist_json else None,
                    validation_passed=validation.valid, activated=activate and validation.valid and persist_db and not validate_only)
        log_structured(self.logger, "regulation_corpus_ingested", corpus_version=version,
                       document_count=summary.document_count, chunk_count=summary.chunk_count,
                       validation_passed=validation.valid, activated=summary.activated)
        return summary

    def _validate(self, documents: list[RegulationDocument], chunks: list[RegulationChunk]) -> CorpusValidation:
        body = [chunk for chunk in chunks if chunk.chunk_type in {"clause", "table"}]
        missing = [chunk for chunk in body if not chunk.clause_id]
        false_headers = [chunk.clause_id or "" for chunk in body if re_false_header(chunk)]
        errors: list[str] = []
        missing_rate = len(missing) / len(body) if body else 1.0
        if missing_rate >= 0.02:
            errors.append(f"clause identifier missing rate {missing_rate:.2%} exceeds limit")
        if false_headers:
            errors.append(f"false header clauses detected: {', '.join(false_headers[:5])}")
        if any(not chunk.page_start or not chunk.page_end or chunk.page_end < chunk.page_start for chunk in chunks):
            errors.append("one or more chunks have an invalid page range")
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            errors.append("duplicate deterministic chunk IDs detected")
        structured_chars = sum(len(clause.content) + sum(len(cell) for table in clause.tables for row in table.rows for cell in row)
                               for document in documents for article in document.articles for clause in article.clauses)
        chunk_chars = sum(len(chunk.content) for chunk in body)
        coverage = min(1.0, chunk_chars / structured_chars) if structured_chars else (1.0 if chunks else 0.0)
        if coverage < 0.98:
            errors.append(f"structured body coverage {coverage:.2%} is below limit")
        return CorpusValidation(valid=not errors, clause_missing_rate=missing_rate,
                                body_coverage_rate=coverage, false_header_clauses=false_headers, errors=errors)

    def _write_artifacts(self, output: Path, documents: list[RegulationDocument], chunks: list[RegulationChunk],
                         manifest: CorpusManifest, emit_markdown: bool) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps([chunk.model_dump(mode="json") for chunk in chunks], ensure_ascii=False, indent=2), encoding="utf-8")
        output.with_name("corpus_manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        structured_dir = output.parent / "structured"
        structured_dir.mkdir(exist_ok=True)
        for document in documents:
            (structured_dir / f"{document.document_key}.json").write_text(document.model_dump_json(indent=2), encoding="utf-8")
            if emit_markdown:
                (structured_dir / f"{document.document_key}.md").write_text(self._render_markdown(document), encoding="utf-8")

    def _render_markdown(self, document: RegulationDocument) -> str:
        lines = [f"# {document.document_title}", ""]
        for article in document.articles:
            lines.extend([f"## {article.article_id}{' ' + article.title if article.title else ''}", ""])
            for clause in article.clauses:
                lines.extend([f"### {clause.clause_id}{' ' + clause.title if clause.title else ''}", ""])
                lines.extend([*clause.paragraphs, *clause.list_items, ""])
                for table in clause.tables:
                    lines.extend([self.chunker._table_markdown(table), ""])
        return "\n\n".join(part for part in lines if part is not None).strip() + "\n"

    def _embed_chunks(self, chunks: list[RegulationChunk]) -> list[list[float]]:
        service = self.embedding_service or build_embedding_service()
        embeddings = service.embed_texts([chunk.embedding_text or chunk.content for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError("Embedding service returned an unexpected number of vectors.")
        return embeddings


def re_false_header(chunk: RegulationChunk) -> bool:
    return bool(chunk.clause_id and chunk.clause_id.count(".") == 0
                and ("2026 Formula 1:" in chunk.content or "©2026" in chunk.content))
