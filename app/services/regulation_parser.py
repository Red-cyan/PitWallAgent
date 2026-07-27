from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path
from typing import cast

from app.schemas.pdf import PdfPage
from app.schemas.regulation_document import RegulationArticle, RegulationClause, RegulationDocument


class RegulationStructureParser:
    VERSION = "clause-tree-v1"
    SECTION_PATTERN = re.compile(r"Section\s+([A-F])", re.IGNORECASE)
    LIST_MARKER = re.compile(r"^(?:[a-z]\.|[ivxlcdm]+\)|\([a-z0-9ivxlcdm]+\))\s*$", re.IGNORECASE)

    def parse(
        self,
        document_title: str,
        pages: list[PdfPage],
        source_path: str | Path | None = None,
    ) -> RegulationDocument:
        section_match = self.SECTION_PATTERN.search(document_title)
        if not section_match:
            raise ValueError(f"Cannot infer regulation section from {document_title!r}")
        section_letter = section_match.group(1).upper()
        section_code = f"Section {section_letter}"
        clause_pattern = re.compile(
            rf"^(?:ARTICLE\s+)?({section_letter}\d+(?:\.\d+)*)(?:\s*:\s*|\s+)?(.*)$",
            re.IGNORECASE,
        )

        articles: OrderedDict[str, dict[str, object]] = OrderedDict()
        current: dict[str, object] | None = None
        pending_title = False
        current_scope: str | None = None

        for page in pages:
            if self._is_contents_page(page.text):
                continue
            source_lines = page.lines or [None] * len(page.text.splitlines())
            text_lines = [line.text for line in page.lines] if page.lines else page.text.splitlines()
            for source_line, raw_line in zip(source_lines, text_lines, strict=True):
                line = " ".join(raw_line.split())
                if not line:
                    continue
                appendix_match = re.match(r"^(APPENDIX\s+[A-F]\d+)\b", line, re.I)
                if appendix_match and (source_line is None or source_line.bold):
                    current_scope = appendix_match.group(1).upper()
                    current = None
                    continue
                match = clause_pattern.fullmatch(line)
                is_heading_style = source_line is None or source_line.bold
                if match and is_heading_style and self._is_valid_identifier(match.group(1), section_letter):
                    if re.match(r"2026\s+Formula\s+1:", match.group(2), re.I):
                        continue
                    clause_id = match.group(1).upper()
                    article_id = clause_id.split(".", 1)[0]
                    article_key = f"{current_scope or 'main'}:{article_id}"
                    article = articles.setdefault(
                        article_key,
                        {"article_id": article_id, "scope": current_scope, "title": None,
                         "page_start": page.page_number, "page_end": page.page_number, "clauses": []},
                    )
                    article["page_end"] = page.page_number
                    current = {
                        "clause_id": clause_id,
                        "article_id": article_id,
                        "page_start": page.page_number,
                        "page_end": page.page_number,
                        "title": match.group(2).strip() or None,
                        "paragraphs": [],
                        "list_items": [],
                        "tables": [],
                        "article_key": article_key,
                        "scope": current_scope,
                    }
                    clauses = article["clauses"]
                    assert isinstance(clauses, list)
                    clauses.append(current)
                    if clause_id == article_id and current["title"]:
                        article["title"] = current["title"]
                    pending_title = not bool(current["title"])
                    continue

                if current is None or self._is_document_noise(line):
                    continue
                current["page_end"] = page.page_number
                article = articles[str(current["article_key"])]
                article["page_end"] = page.page_number
                if pending_title and self._looks_like_title(line):
                    current["title"] = line
                    if current["clause_id"] == current["article_id"]:
                        article["title"] = line
                    pending_title = False
                    continue
                pending_title = False
                self._append_body_line(current, line)

            if current is not None and page.tables:
                tables = current["tables"]
                assert isinstance(tables, list)
                tables.extend(page.tables)
                current["page_end"] = page.page_number

        parsed_articles: list[RegulationArticle] = []
        for raw_article in articles.values():
            article_id = str(raw_article["article_id"])
            raw_clauses = raw_article["clauses"]
            assert isinstance(raw_clauses, list)
            article_title = raw_article["title"] if isinstance(raw_article["title"], str) else None
            clauses = [self._to_clause(item, article_title) for item in raw_clauses if self._has_body(item)]
            if clauses:
                parsed_articles.append(
                    RegulationArticle(
                        article_id=article_id,
                        title=article_title,
                        page_start=cast(int, raw_article["page_start"]),
                        page_end=cast(int, raw_article["page_end"]),
                        clauses=clauses,
                        scope=raw_article["scope"] if isinstance(raw_article["scope"], str) else None,
                    )
                )

        return RegulationDocument(
            document_key=self.document_key(document_title),
            document_title=document_title,
            section_code=section_code,
            source_path=str(source_path) if source_path is not None else None,
            page_count=len(pages),
            articles=parsed_articles,
        )

    def document_key(self, title: str) -> str:
        section = self.SECTION_PATTERN.search(title)
        return f"fia-2026-section-{section.group(1).lower()}" if section else re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")

    def _append_body_line(self, clause: dict[str, object], line: str) -> None:
        paragraphs = clause["paragraphs"]
        list_items = clause["list_items"]
        assert isinstance(paragraphs, list) and isinstance(list_items, list)
        if self.LIST_MARKER.fullmatch(line):
            list_items.append(line)
        elif list_items and self.LIST_MARKER.fullmatch(str(list_items[-1])):
            list_items[-1] = f"{list_items[-1]} {line}"
        elif list_items and re.match(r"^(?:[a-z]\.|[ivxlcdm]+\)|\([^)]+\))\s", str(list_items[-1]), re.I):
            list_items[-1] = f"{list_items[-1]} {line}"
        elif paragraphs:
            paragraphs[-1] = f"{paragraphs[-1]} {line}"
        else:
            paragraphs.append(line)

    def _to_clause(self, raw: dict[str, object], article_title: str | None) -> RegulationClause:
        clause_id = str(raw["clause_id"])
        return RegulationClause(
            clause_id=clause_id,
            title=raw["title"] if isinstance(raw["title"], str) else None,
            article_id=str(raw["article_id"]),
            article_title=article_title,
            level=clause_id.count(".") + 1,
            page_start=cast(int, raw["page_start"]),
            page_end=cast(int, raw["page_end"]),
            paragraphs=cast(list[str], raw["paragraphs"]),
            list_items=cast(list[str], raw["list_items"]),
            tables=cast(list, raw["tables"]),
            scope=raw["scope"] if isinstance(raw["scope"], str) else None,
        )

    def _has_body(self, raw: dict[str, object]) -> bool:
        return bool(raw["title"] or raw["paragraphs"] or raw["list_items"] or raw["tables"])

    def _is_valid_identifier(self, identifier: str, section_letter: str) -> bool:
        return identifier.startswith(section_letter) and bool(re.fullmatch(r"[A-F]\d+(?:\.\d+)*", identifier, re.I))

    def _looks_like_title(self, line: str) -> bool:
        return len(line) <= 120 and not line.endswith((".", ";", ":")) and len(line.split()) <= 16

    def _is_contents_page(self, text: str) -> bool:
        upper = text.upper()
        if "CONTENTS:" in upper or "CONVENTION:" in upper:
            return True
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        index_ids = sum(bool(re.fullmatch(r"(?:ARTICLE\s+)?[A-F]\d+(?:\.\d+)*:?.*", line, re.I)) for line in lines)
        page_numbers = sum(bool(re.fullmatch(r"\d{1,3}", line)) for line in lines)
        sentence_lines = sum(len(line) > 60 and line.endswith((".", ";")) for line in lines)
        dense_index = index_ids / max(len(lines), 1) >= 0.18
        return index_ids >= 3 and (page_numbers >= max(3, index_ids // 2) or (dense_index and sentence_lines <= 2))

    def _is_document_noise(self, line: str) -> bool:
        return bool(
            re.fullmatch(r"(?:SECTION [A-F].*|[0-9]+ [A-F])", line, re.I)
            or line.startswith("2026 Formula 1:")
            or line.startswith("©2026")
            or line.startswith(("Issue ", "Status:", "Date:", "WMSC approval date:"))
        )
