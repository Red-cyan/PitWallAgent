from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.schemas.chunk import RegulationChunk
from app.schemas.pdf import PdfPage, PdfTable
from app.schemas.regulation_document import RegulationDocument
from app.services.regulation_parser import RegulationStructureParser


class RegulationChunker:
    SECTION_PATTERN = re.compile(r"(Section\s+[A-F])", re.IGNORECASE)
    ARTICLE_PATTERN = re.compile(r"^(ARTICLE\s+\d+[A-Z]?(?:\.\d+)*|[A-F]\d+(?:\.\d+)*)\b", re.I)

    def __init__(self, parser: RegulationStructureParser | None = None) -> None:
        self.parser = parser or RegulationStructureParser()

    def chunk_pages(self, pages: list[PdfPage], max_chars: int = 1600) -> list[RegulationChunk]:
        return self.chunk_document("Unknown document", pages, max_chars=max_chars)

    def chunk_document(
        self,
        document_title: str,
        pages: list[PdfPage],
        max_chars: int = 1600,
        source_path: str | Path | None = None,
        corpus_version: str = "legacy",
    ) -> list[RegulationChunk]:
        try:
            document = self.parser.parse(document_title, pages, source_path)
        except ValueError:
            return self._legacy_chunks(document_title, pages, max_chars, source_path, corpus_version)
        chunks = self.chunk_structure(document, corpus_version=corpus_version, max_chars=max_chars)
        return chunks or self._legacy_chunks(document_title, pages, max_chars, source_path, corpus_version)

    def chunk_structure(
        self,
        document: RegulationDocument,
        *,
        corpus_version: str,
        max_chars: int = 1600,
    ) -> list[RegulationChunk]:
        chunks: list[RegulationChunk] = []
        chunk_index = 1
        occurrence_counts: dict[tuple[str | None, str], int] = {}
        for article in document.articles:
            index_lines = [
                f"- {clause.clause_id}{': ' + clause.title if clause.title else ''}"
                for clause in article.clauses
                if clause.clause_id != article.article_id
            ]
            for clause in article.clauses:
                occurrence_key = (clause.scope, clause.clause_id)
                occurrence_counts[occurrence_key] = occurrence_counts.get(occurrence_key, 0) + 1
                occurrence_ordinal = occurrence_counts[occurrence_key]
                units = [
                    " ".join(part for part in (clause.clause_id, clause.title) if part),
                    *clause.paragraphs,
                    *clause.list_items,
                ]
                parts = self._split_units([unit for unit in units if unit], max_chars)
                for part_ordinal, content in enumerate(parts, start=1):
                    chunks.append(
                        self._build_chunk(
                            document, article.article_id, article.title, clause.clause_id,
                            "clause", content, clause.page_start, clause.page_end,
                            part_ordinal, chunk_index, corpus_version, clause.scope, occurrence_ordinal,
                        )
                    )
                    chunk_index += 1
                table_part_ordinal = 1
                for table in clause.tables:
                    for content in self._table_parts(table, max_chars):
                        chunks.append(
                            self._build_chunk(
                                document, article.article_id, article.title, clause.clause_id,
                                "table", content, table.page_number, table.page_number,
                                table_part_ordinal, chunk_index, corpus_version, clause.scope, occurrence_ordinal,
                            )
                        )
                        table_part_ordinal += 1
                        chunk_index += 1
            if index_lines:
                overview_units = [f"{article.article_id}{' ' + article.title if article.title else ''}", *index_lines]
                for part_ordinal, content in enumerate(self._split_units(overview_units, max_chars), start=1):
                    chunks.append(
                        self._build_chunk(
                            document, article.article_id, article.title, article.article_id,
                            "article_overview", content, article.page_start, article.page_end,
                            part_ordinal, chunk_index, corpus_version, article.scope,
                        )
                    )
                    chunk_index += 1
        return chunks

    def _build_chunk(
        self,
        document: RegulationDocument,
        article_id: str,
        article_title: str | None,
        clause_id: str,
        chunk_type: str,
        content: str,
        page_start: int,
        page_end: int,
        part_ordinal: int,
        chunk_index: int,
        corpus_version: str,
        scope: str | None = None,
        occurrence_ordinal: int = 1,
    ) -> RegulationChunk:
        article_heading = " ".join((article_id, article_title)) if article_title else None
        heading_path = [document.section_code, scope, article_heading, clause_id]
        heading_path = list(dict.fromkeys(part for part in heading_path if part))
        id_part = re.sub(r"[^a-z0-9.]+", "-", clause_id.lower()).strip("-")
        title_slug = re.sub(r"[^a-z0-9]+", "-", document.document_title.lower()).strip("-")
        scope_id = re.sub(r"[^a-z0-9]+", "-", scope.lower()).strip("-") if scope else "main"
        occurrence_id = f":o{occurrence_ordinal:02d}" if occurrence_ordinal > 1 else ""
        chunk_id = f"{title_slug}:{corpus_version}:{scope_id}:{id_part}{occurrence_id}:{chunk_type}:p{part_ordinal:02d}"
        breadcrumb = " > ".join(heading_path)
        return RegulationChunk(
            chunk_id=chunk_id,
            corpus_version=corpus_version,
            document_key=document.document_key,
            document_title=document.document_title,
            section_code=document.section_code,
            article=clause_id,
            article_title=article_title,
            clause_id=clause_id,
            chunk_type=chunk_type,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            embedding_text=f"{breadcrumb}\n\n{content}",
            page_number=page_start,
            page_start=page_start,
            page_end=page_end,
            heading_path=heading_path,
            chunk_index=chunk_index,
            part_ordinal=part_ordinal,
            content=content,
            source_path=document.source_path,
        )

    def _split_units(self, units: list[str], max_chars: int) -> list[str]:
        expanded: list[str] = []
        for unit in units:
            if len(unit) <= max_chars:
                expanded.append(unit)
                continue
            expanded.extend(self._split_long_unit(unit, max_chars))

        parts: list[str] = []
        current: list[str] = []
        for unit in expanded:
            projected = len("\n\n".join([*current, unit]))
            if current and projected > max_chars:
                parts.append("\n\n".join(current))
                current = []
            current.append(unit)
        if current:
            parts.append("\n\n".join(current))
        return parts

    def _split_long_unit(self, unit: str, max_chars: int) -> list[str]:
        semantic_units = re.split(
            r"(?<=[.!?;:])\s+|(?=[\"“][A-Z][^\"”]{0,100}[\"”]\s+means\b)",
            unit,
        )
        result: list[str] = []
        for semantic_unit in (part.strip() for part in semantic_units if part.strip()):
            while len(semantic_unit) > max_chars:
                candidates = [semantic_unit.rfind(mark, 0, max_chars + 1) for mark in ("; ", ": ", ", ", " ")]
                split_at = max(candidates)
                if split_at <= 0:
                    break
                result.append(semantic_unit[:split_at + 1].strip())
                semantic_unit = semantic_unit[split_at + 1:].strip()
            if semantic_unit:
                result.append(semantic_unit)
        return result

    def _table_parts(self, table: PdfTable, max_chars: int) -> list[str]:
        width = max([len(table.headers), *(len(row) for row in table.rows)], default=0)
        if width == 0:
            return []
        headers = (table.headers + [""] * width)[:width]
        prefix = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * width) + " |"]
        parts: list[str] = []
        rows: list[str] = []
        for row in table.rows:
            rendered = "| " + " | ".join((row + [""] * width)[:width]) + " |"
            if rows and len("\n".join([*prefix, *rows, rendered])) > max_chars:
                parts.append("\n".join([*prefix, *rows]))
                rows = []
            if len("\n".join([*prefix, rendered])) > max_chars:
                parts.extend(self._split_long_unit(rendered, max_chars))
            else:
                rows.append(rendered)
        if rows or not parts:
            parts.append("\n".join([*prefix, *rows]))
        return parts

    def _table_markdown(self, table: PdfTable) -> str:
        width = max([len(table.headers), *(len(row) for row in table.rows)], default=0)
        if width == 0:
            return ""
        headers = (table.headers + [""] * width)[:width]
        lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * width) + " |"]
        lines.extend("| " + " | ".join((row + [""] * width)[:width]) + " |" for row in table.rows)
        return "\n".join(lines)

    def _legacy_chunks(
        self,
        document_title: str,
        pages: list[PdfPage],
        max_chars: int,
        source_path: str | Path | None,
        corpus_version: str,
    ) -> list[RegulationChunk]:
        chunks: list[RegulationChunk] = []
        section = self._extract_section_code(document_title)
        document_key = self.parser.document_key(document_title)
        current_article: str | None = None
        for page in pages:
            if "CONTENTS:" in page.text.upper():
                continue
            groups: list[tuple[str | None, list[str]]] = []
            for line in [line.strip() for line in page.text.splitlines() if line.strip()]:
                match = self.ARTICLE_PATTERN.match(line)
                if match:
                    current_article = match.group(1).upper()
                    groups.append((current_article, [line]))
                elif groups:
                    groups[-1][1].append(line)
            for article, lines in groups:
                for part_ordinal, content in enumerate(self._split_units(lines, max_chars), start=1):
                    digest = hashlib.sha256(content.encode()).hexdigest()
                    chunks.append(RegulationChunk(
                        chunk_id=f"{re.sub(r'[^a-z0-9]+', '-', document_title.lower()).strip('-')}:{corpus_version}:{(article or 'unknown').lower().replace(' ', '-')}:clause:p{part_ordinal:02d}",
                        document_title=document_title, section_code=section, article=article,
                        clause_id=article, page_number=page.page_number, page_start=page.page_number,
                        page_end=page.page_number, heading_path=[x for x in (section, article) if x],
                        chunk_index=len(chunks) + 1, content=content, source_path=str(source_path) if source_path else None,
                        corpus_version=corpus_version, document_key=document_key, content_hash=digest,
                        embedding_text=f"{section or ''} > {article or ''}\n\n{content}", part_ordinal=part_ordinal,
                    ))
        return chunks

    def _extract_section_code(self, document_title: str) -> str | None:
        match = self.SECTION_PATTERN.search(document_title)
        return match.group(1).title() if match else None
