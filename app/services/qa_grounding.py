"""Deterministic grounding checks for RAG answers.

These helpers measure how well an answer is anchored to its retrieved evidence
without calling an LLM. They are used by the QA evaluation in offline (CI-safe)
mode and complement the LLM-as-judge in online mode:

- ``evidence_supported_fraction``: fraction of answer sentences that overlap
  with the evidence (lexical grounding, CJK-aware).
- ``citations_consistent``: every citation must point to a retrieved chunk.
"""

from __future__ import annotations

import re
from typing import Any

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
WORD_RE = re.compile(r"[a-z0-9]+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])")


def tokenize(text: str) -> set[str]:
    """Tokenize text into CJK bigrams and ascii words (lowercase)."""
    lowered = text.lower()
    tokens: set[str] = set()
    tokens.update(word for word in WORD_RE.findall(lowered) if len(word) >= 3)
    cjk_chars = [char for char in lowered if CJK_RE.match(char)]
    tokens.update("".join(pair) for pair in zip(cjk_chars, cjk_chars[1:]))
    return tokens


def sentence_split(text: str) -> list[str]:
    """Split text into sentences on Chinese/English sentence endings."""
    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    return sentences


def evidence_supported_fraction(
    answer: str,
    evidence_texts: list[str],
    min_overlap_ratio: float = 0.2,
) -> float:
    """Fraction of answer sentences whose tokens substantially overlap the evidence.

    Sentences with fewer than two tokens are ignored (they carry little
    information). Returns 1.0 when there are no analyzable sentences.
    """
    if not evidence_texts:
        return 0.0

    evidence_token_sets = [tokenize(text) for text in evidence_texts]
    analyzable = 0
    supported = 0
    for sentence in sentence_split(answer):
        tokens = tokenize(sentence)
        if len(tokens) < 2:
            continue
        analyzable += 1
        best_overlap = max(
            len(tokens & evidence_tokens) / len(tokens)
            for evidence_tokens in evidence_token_sets
        )
        if best_overlap >= min_overlap_ratio:
            supported += 1

    return supported / analyzable if analyzable else 1.0


def _normalize_article(article: str | None) -> str:
    return re.sub(r"\s+", "", article or "").lower()


def citation_matches_chunk(citation: Any, chunk: Any) -> bool:
    """Return True when a citation points at the given retrieved chunk."""
    cited_article = _normalize_article(getattr(citation, "article", None))
    chunk_article = _normalize_article(getattr(chunk, "article", None))
    if cited_article and chunk_article:
        return cited_article == chunk_article
    if cited_article or chunk_article:
        return False

    cited_title = (getattr(citation, "document_title", None) or "").lower()
    chunk_title = (getattr(chunk, "document_title", None) or "").lower()
    if not cited_title or not chunk_title:
        return True
    return cited_title in chunk_title or chunk_title in cited_title


def citations_consistent(citations: list[Any], chunks: list[Any]) -> bool:
    """Return True when every citation matches at least one retrieved chunk."""
    if not citations:
        return True
    return all(
        any(citation_matches_chunk(citation, chunk) for chunk in chunks)
        for citation in citations
    )
