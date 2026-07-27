# ruff: noqa: E402
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Protocol

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.repositories.rule_repository import RuleRepository
from app.schemas.rules import RetrievedChunk


DEFAULT_CASES_PATH = Path("data/evals/rag_cases.jsonl")
RetrievalMode = Literal["keyword", "vector", "hybrid"]


class SearchRepository(Protocol):
    def search(self, question: str, *, mode: RetrievalMode, top_k: int) -> list[RetrievedChunk]: ...


@dataclass(frozen=True)
class RagCase:
    name: str
    question: str
    expected_sections: list[str]
    expected_articles: list[str] | None = None
    accepted_chunk_ids: list[str] | None = None
    expect_evidence: bool = True
    language: str = "en"


@dataclass(frozen=True)
class RagCaseResult:
    name: str
    matched_rank: int | None
    section_matched_rank: int | None
    retrieved_sections: list[str]
    retrieved_articles: list[str]
    retrieved_chunk_ids: list[str]
    passed: bool


def load_cases(path: Path) -> list[RagCase]:
    with path.open("r", encoding="utf-8") as file:
        return [RagCase(**json.loads(line)) for line in file if line.strip()]


def evaluate(
    repository: SearchRepository,
    cases: list[RagCase],
    top_k: int,
    mode: RetrievalMode = "keyword",
) -> tuple[dict[str, float | int | str], list[RagCaseResult]]:
    results: list[RagCaseResult] = []
    positive_ranks: list[int | None] = []
    section_ranks: list[int | None] = []
    clause_hits: list[bool] = []
    negative_passes: list[bool] = []

    for case in cases:
        chunks = repository.search(case.question, mode=mode, top_k=top_k)
        sections = [chunk.section or _section_from_title(chunk.document_title) for chunk in chunks]
        section_rank = _first_rank(sections, case.expected_sections)
        matched_rank = _evidence_rank(chunks, case)
        if case.expect_evidence:
            passed = matched_rank is not None
            positive_ranks.append(matched_rank)
            section_ranks.append(section_rank)
            if case.expected_articles or case.accepted_chunk_ids:
                clause_hits.append(matched_rank is not None)
        else:
            passed = not any(chunk.score_components.get("evidence_strength") == 1.0 for chunk in chunks)
            negative_passes.append(passed)
        results.append(
            RagCaseResult(
                name=case.name,
                matched_rank=matched_rank,
                section_matched_rank=section_rank,
                retrieved_sections=sections,
                retrieved_articles=[chunk.article or "" for chunk in chunks],
                retrieved_chunk_ids=[chunk.chunk_id for chunk in chunks],
                passed=passed,
            )
        )

    positive_count = len(positive_ranks)
    metrics: dict[str, float | int | str] = {
        "mode": mode,
        "cases": len(cases),
        "positive_cases": positive_count,
        "recall_at_1": _ratio(sum(rank == 1 for rank in positive_ranks), positive_count),
        "recall_at_5": _ratio(sum(rank is not None and rank <= 5 for rank in positive_ranks), positive_count),
        "section_recall_at_5": _ratio(sum(rank is not None and rank <= 5 for rank in section_ranks), positive_count),
        "mrr": sum(1 / rank for rank in positive_ranks if rank is not None) / positive_count if positive_count else 0.0,
        "clause_hit_rate": _ratio(sum(clause_hits), len(clause_hits)),
        "strong_evidence_rejection_rate": _ratio(sum(negative_passes), len(negative_passes)),
    }
    return metrics, results


def _evidence_rank(chunks: list[RetrievedChunk], case: RagCase) -> int | None:
    accepted_ids = set(case.accepted_chunk_ids or [])
    expected_articles = {article.lower() for article in case.expected_articles or []}
    expected_sections = set(case.expected_sections)
    for rank, chunk in enumerate(chunks, start=1):
        if accepted_ids and chunk.chunk_id in accepted_ids:
            return rank
        if expected_articles and chunk.article and chunk.article.lower() in expected_articles:
            return rank
        if not accepted_ids and not expected_articles:
            section = chunk.section or _section_from_title(chunk.document_title)
            if section in expected_sections:
                return rank
    return None


def _first_rank(values: list[str], expected: list[str]) -> int | None:
    return next((rank for rank, value in enumerate(values, start=1) if value in expected), None)


def _section_from_title(title: str) -> str:
    for code in "ABCDEF":
        section = f"Section {code}"
        if section.lower() in title.lower():
            return section
    return ""


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def render_markdown(metrics: dict[str, float | int | str], results: list[RagCaseResult]) -> str:
    failures = [result for result in results if not result.passed]
    lines = [
        "# Offline RAG Evaluation",
        "",
        f"- Mode: {metrics['mode']}",
        f"- Cases: {metrics['cases']}",
        f"- Recall@1: {float(metrics['recall_at_1']):.2%}",
        f"- Recall@5: {float(metrics['recall_at_5']):.2%}",
        f"- MRR: {float(metrics['mrr']):.4f}",
        f"- Clause hit rate: {float(metrics['clause_hit_rate']):.2%}",
        f"- Strong-evidence rejection rate: {float(metrics['strong_evidence_rejection_rate']):.2%}",
        "",
        "## Failures",
        "",
    ]
    if not failures:
        lines.append("None.")
    else:
        lines.extend(
            f"- `{result.name}`: retrieved {', '.join(result.retrieved_chunk_ids) or 'no evidence'}"
            for result in failures
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run clause-level RAG retrieval evaluation.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--mode", choices=("keyword", "vector", "hybrid"), default="keyword")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-recall-at-1", type=float, default=0.0)
    parser.add_argument("--min-recall-at-5", "--min-recall", dest="min_recall_at_5", type=float, default=0.85)
    parser.add_argument("--min-clause-hit-rate", type=float, default=0.0)
    parser.add_argument(
        "--min-rejection-rate",
        "--min-strong-evidence-rejection-rate",
        dest="min_rejection_rate",
        type=float,
        default=1.0,
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    mode: RetrievalMode = args.mode
    metrics, results = evaluate(
        RuleRepository(prefer_database=mode != "keyword"),
        load_cases(args.cases),
        args.top_k,
        mode,
    )
    payload = {"metrics": metrics, "results": [asdict(result) for result in results]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(metrics, results), encoding="utf-8")

    passed = (
        float(metrics["recall_at_1"]) >= args.min_recall_at_1
        and float(metrics["recall_at_5"]) >= args.min_recall_at_5
        and float(metrics["clause_hit_rate"]) >= args.min_clause_hit_rate
        and float(metrics["strong_evidence_rejection_rate"]) >= args.min_rejection_rate
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
