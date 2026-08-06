# ruff: noqa: E402
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_reconfigure = getattr(sys.stdout, "reconfigure", None)
if _reconfigure is not None:
    _reconfigure(encoding="utf-8")

from app.config.settings import settings
from app.rag.retrieval.query_rewriter import QueryRewriter
from app.repositories.rule_repository import RuleRepository
from app.schemas.rules import RuleAskRequest
from app.services.llm.client import LLMClient
from app.services.qa_grounding import citations_consistent, evidence_supported_fraction
from app.services.qa_service import RegulationQAService

DEFAULT_CASES_PATH = Path("data/evals/qa_cases.jsonl")
DEFAULT_CHUNKS_FILE = Path("data/regulations/processed/chunks.json")

settings.regulation_rerank_enabled = False
settings.regulation_vector_retrieval_enabled = False


class DeterministicQueryRewriter(QueryRewriter):
    """Rewriter that skips the LLM so offline eval is fully deterministic."""

    def rewrite(self, question: str) -> list[str]:
        return []


class FailingLLMClient(LLMClient):
    """LLM client that always fails, forcing the deterministic fallback path."""

    def __init__(self) -> None:
        pass

    def chat(self, messages: list[dict], temperature: float = 0.2, max_tokens: int | None = None, timeout: float | None = None, response_format: Any | None = None) -> str:
        raise RuntimeError("offline eval mode: LLM disabled")

    def stream_chat(self, messages: list[dict], temperature: float = 0.2, max_tokens: int | None = None, timeout: float | None = None):
        raise RuntimeError("offline eval mode: LLM disabled")
        yield ""


@dataclass(frozen=True)
class QACase:
    name: str
    question: str
    expected_answer_status: str
    language: str = "en"


@dataclass
class QAResult:
    name: str
    question: str
    answer: str
    answer_status: str
    expected_answer_status: str
    evidence_count: int
    status_correct: bool
    citations_consistent: bool
    evidence_supported_fraction: float
    groundedness_score: int | None = None
    helpfulness_score: int | None = None
    rejection_correct: bool | None = None
    violations: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def load_cases(path: Path) -> list[QACase]:
    cases: list[QACase] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            try:
                cases.append(
                    QACase(
                        name=payload["name"],
                        question=payload["question"],
                        expected_answer_status=payload["expected_answer_status"],
                        language=payload.get("language", "en"),
                    )
                )
            except KeyError as exc:
                raise ValueError(f"Invalid QA eval case at {path}:{line_number}: missing {exc.args[0]}") from exc
    return cases


class AnswerJudge(Protocol):
    def judge(
        self,
        question: str,
        answer: str,
        evidence_texts: list[str],
        expected_answer_status: str,
    ) -> Any: ...


def evaluate(
    qa_service: RegulationQAService,
    cases: list[QACase],
    *,
    use_judge: bool = False,
    judge: AnswerJudge | None = None,
) -> tuple[dict[str, float | int | str], list[QAResult]]:
    results: list[QAResult] = []
    for case in cases:
        response = qa_service.ask(RuleAskRequest(question=case.question))
        result = QAResult(
            name=case.name,
            question=case.question,
            answer=response.answer,
            answer_status=response.answer_status,
            expected_answer_status=case.expected_answer_status,
            evidence_count=response.evidence_count,
            status_correct=response.answer_status == case.expected_answer_status,
            citations_consistent=citations_consistent(response.citations, response.retrieved_chunks),
            evidence_supported_fraction=evidence_supported_fraction(
                response.answer,
                [chunk.content for chunk in response.retrieved_chunks],
            ),
        )
        if not result.status_correct:
            result.failures.append(
                f"status expected={case.expected_answer_status} actual={response.answer_status}"
            )
        if response.answer_status == "answered" and not result.citations_consistent:
            result.failures.append("citations do not match retrieved chunks")

        if use_judge and judge is not None:
            try:
                verdict = judge.judge(
                    question=case.question,
                    answer=response.answer,
                    evidence_texts=[chunk.content for chunk in response.retrieved_chunks],
                    expected_answer_status=response.answer_status,
                )
            except Exception as exc:
                result.failures.append(f"judge_error={exc.__class__.__name__}")
                verdict = None
            if verdict is not None:
                result.groundedness_score = verdict.groundedness_score
                result.helpfulness_score = verdict.helpfulness_score
                result.rejection_correct = verdict.rejection_correct
                result.violations = verdict.violations
                if verdict.groundedness_score < 4:
                    result.failures.append(f"groundedness={verdict.groundedness_score}")
                if verdict.rejection_correct is False:
                    result.failures.append("rejection decision incorrect")

        results.append(result)

    metrics: dict[str, float | int | str] = {
        "mode": "online" if use_judge else "offline",
        "cases": len(results),
        "answer_status_accuracy": _rate([r.status_correct for r in results]),
        "citation_consistency_rate": _rate([r.citations_consistent for r in results]),
        "mean_evidence_supported_fraction": _mean([r.evidence_supported_fraction for r in results]),
    }
    groundedness = [r.groundedness_score for r in results if r.groundedness_score is not None]
    helpfulness = [r.helpfulness_score for r in results if r.helpfulness_score is not None]
    rejection = [r.rejection_correct for r in results if r.rejection_correct is not None]
    if groundedness:
        metrics["mean_groundedness_score"] = _mean([float(score) for score in groundedness])
        metrics["groundedness_pass_rate"] = _rate([score >= 4 for score in groundedness])
    if helpfulness:
        metrics["mean_helpfulness_score"] = _mean([float(score) for score in helpfulness])
    if rejection:
        metrics["rejection_correct_rate"] = _rate(list(rejection))
    return metrics, results


def _rate(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 1.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def render_markdown(metrics: dict[str, float | int | str], results: list[QAResult]) -> str:
    failures = [result for result in results if result.failures]
    lines = [
        "# End-to-end QA Evaluation",
        "",
        f"- Mode: {metrics['mode']}",
        f"- Cases: {metrics['cases']}",
        f"- Answer-status accuracy: {float(metrics['answer_status_accuracy']):.2%}",
        f"- Citation consistency rate: {float(metrics['citation_consistency_rate']):.2%}",
        f"- Mean evidence-supported fraction: {float(metrics['mean_evidence_supported_fraction']):.3f}",
    ]
    if "mean_groundedness_score" in metrics:
        lines.append(f"- Mean groundedness score: {float(metrics['mean_groundedness_score']):.2f}")
        lines.append(f"- Groundedness pass rate (>=4): {float(metrics['groundedness_pass_rate']):.2%}")
    if "mean_helpfulness_score" in metrics:
        lines.append(f"- Mean helpfulness score: {float(metrics['mean_helpfulness_score']):.2f}")
    if "rejection_correct_rate" in metrics:
        lines.append(f"- Rejection correctness rate: {float(metrics['rejection_correct_rate']):.2%}")
    lines.extend(["", "## Failures", ""])
    if not failures:
        lines.append("None.")
    else:
        lines.extend(
            f"- `{result.name}`: {'; '.join(result.failures)}"
            for result in failures
        )
    return "\n".join(lines) + "\n"


def _check(metrics: dict[str, float | int | str], args: argparse.Namespace) -> bool:
    passed = True
    checks = [
        ("min_status_accuracy", "answer_status_accuracy"),
        ("min_citation_consistency", "citation_consistency_rate"),
    ]
    for threshold_arg, metric_key in checks:
        threshold = getattr(args, threshold_arg)
        value = float(metrics.get(metric_key, 0.0))
        if value < threshold:
            print(f"FAIL {metric_key}: {value:.2%} < {threshold:.2%}")
            passed = False
    for threshold_arg, metric_key in (
        ("min_groundedness_score", "mean_groundedness_score"),
        ("min_helpfulness_score", "mean_helpfulness_score"),
    ):
        threshold = getattr(args, threshold_arg)
        if threshold is not None:
            value = float(metrics.get(metric_key, 0.0))
            if value < threshold:
                print(f"FAIL {metric_key}: {value:.2f} < {threshold}")
                passed = False
    if args.min_rejection_correct is not None:
        value = float(metrics.get("rejection_correct_rate", 0.0))
        if value < args.min_rejection_correct:
            print(f"FAIL rejection_correct_rate: {value:.2%} < {args.min_rejection_correct:.2%}")
            passed = False
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Run end-to-end answer quality evaluation.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--chunks-file", type=Path, default=DEFAULT_CHUNKS_FILE)
    parser.add_argument("--mode", choices=("offline", "online"), default="offline")
    parser.add_argument("--min-status-accuracy", type=float, default=0.95)
    parser.add_argument("--min-citation-consistency", type=float, default=1.0)
    parser.add_argument("--min-groundedness-score", type=float, default=None)
    parser.add_argument("--min-helpfulness-score", type=float, default=None)
    parser.add_argument("--min-rejection-correct", type=float, default=None)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    repository = RuleRepository(prefer_database=False, chunks_file=args.chunks_file)
    qa_service = RegulationQAService(repository=repository)

    judge = None
    if args.mode == "online":
        from app.services.llm.judge import LLMJudge

        judge = LLMJudge()
    else:
        repository = RuleRepository(
            query_rewriter=DeterministicQueryRewriter(),
            prefer_database=False,
            chunks_file=args.chunks_file,
        )
        qa_service = RegulationQAService(repository=repository, llm_client=FailingLLMClient())

    metrics, results = evaluate(qa_service, load_cases(args.cases), use_judge=args.mode == "online", judge=judge)
    payload = {"metrics": metrics, "results": [asdict(result) for result in results]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(metrics, results), encoding="utf-8")

    return 0 if _check(metrics, args) and len(results) == len(load_cases(args.cases)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
