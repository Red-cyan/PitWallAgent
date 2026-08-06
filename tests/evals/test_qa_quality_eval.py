from __future__ import annotations

from pathlib import Path

from app.schemas.rules import (
    Citation,
    RetrievedChunk,
    RuleAskRequest,
    RuleAskResponse,
)
from app.services.qa_grounding import (
    citations_consistent,
    evidence_supported_fraction,
)
from scripts.run_qa_eval import QACase, evaluate, load_cases, render_markdown


class StubQAService:
    def ask(self, request: RuleAskRequest) -> RuleAskResponse:
        if "外星" in request.question or "extraterrestrial" in request.question.lower():
            return RuleAskResponse(
                answer="未检索到相关 FIA 规则证据。为了避免编造规则，我不能基于当前资料给出确定答案。",
                answer_status="insufficient_evidence",
                confidence="low",
                evidence_count=0,
                source_mode="regulation_rag",
                query_type="fact_lookup",
            )
        return RuleAskResponse(
            answer="不安全释放指赛车在放行时危及维修区人员或他人的情况，依据是 Section B 条款 (4)。",
            answer_status="answered",
            confidence="medium",
            evidence_count=1,
            source_mode="regulation_rag",
            query_type="fact_lookup",
            citations=[
                Citation(
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting]",
                    article="(4)",
                    page=9,
                )
            ],
            retrieved_chunks=[
                RetrievedChunk(
                    chunk_id="chunk-1",
                    content="Unsafe release occurs when a car is released in a way that endangers pit lane personnel or another driver.",
                    score=12.0,
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting]",
                    article="(4)",
                    page=9,
                )
            ],
        )


def test_load_cases_reads_jsonl(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        '{"name":"red-flag","question":"What is a red flag?","expected_answer_status":"answered"}\n',
        encoding="utf-8",
    )

    cases = load_cases(cases_path)

    assert cases == [QACase("red-flag", "What is a red flag?", "answered")]


def test_real_qa_cases_dataset_is_balanced() -> None:
    cases = load_cases(Path("data/evals/qa_cases.jsonl"))

    assert len(cases) == 21
    answered = [case for case in cases if case.expected_answer_status == "answered"]
    partial = [case for case in cases if case.expected_answer_status == "partial_evidence"]
    insufficient = [case for case in cases if case.expected_answer_status == "insufficient_evidence"]
    assert len(answered) == 17
    assert len(partial) == 1
    assert len(insufficient) == 3


def test_evaluate_reports_status_accuracy_and_citation_consistency() -> None:
    cases = [
        QACase("answered", "What is an unsafe release?", "answered"),
        QACase("insufficient", "外星人赛车该怎么处理？", "insufficient_evidence"),
    ]

    metrics, results = evaluate(StubQAService(), cases)  # type: ignore[arg-type]

    assert metrics["answer_status_accuracy"] == 1.0
    assert metrics["citation_consistency_rate"] == 1.0
    assert all(not result.failures for result in results)
    assert "Answer-status accuracy: 100.00%" in render_markdown(metrics, results)


def test_evaluate_flags_status_mismatch() -> None:
    class WrongStatusService(StubQAService):
        def ask(self, request: RuleAskRequest) -> RuleAskResponse:
            response = super().ask(request)
            if response.answer_status == "insufficient_evidence":
                return RuleAskResponse(
                    answer="外星人赛车会适用统一的外星赛规。",
                    answer_status="answered",
                    confidence="medium",
                    evidence_count=0,
                    source_mode="regulation_rag",
                    query_type="fact_lookup",
                )
            return response

    metrics, results = evaluate(WrongStatusService(), [QACase("x", "外星人赛车该怎么处理？", "insufficient_evidence")])  # type: ignore[arg-type]

    assert metrics["answer_status_accuracy"] == 0.0
    assert results[0].failures


def test_evidence_supported_fraction_high_for_grounded_answer() -> None:
    evidence = [
        "A red flag suspends the race; all cars must return to the pits slowly and stop."
    ]

    grounded = "A red flag suspends the race and the cars must return to the pits slowly and stop."
    fabricated = "Aliens receive fifty extra championship points and skip the next qualifying session."

    assert evidence_supported_fraction(grounded, evidence) > 0.4
    assert evidence_supported_fraction(fabricated, evidence) < 0.2


def test_evidence_supported_fraction_zero_without_evidence() -> None:
    assert evidence_supported_fraction("比赛暂停程序是出示红旗。", []) == 0.0


def test_citations_consistent_matches_retrieved_chunks() -> None:
    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            content="unsafe release text",
            document_title="FIA 2026 F1 Regulations - Section B [Sporting]",
            article="(4)",
            page=9,
        )
    ]
    matching = Citation(document_title="Section B", article="(4)", page=9)
    mismatching = Citation(document_title="Section A", article="A1.1", page=5)

    assert citations_consistent([matching], chunks) is True
    assert citations_consistent([mismatching], chunks) is False


def test_citations_consistent_vacuously_true_when_empty() -> None:
    assert citations_consistent([], []) is True
