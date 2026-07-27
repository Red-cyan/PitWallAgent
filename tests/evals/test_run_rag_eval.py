from pathlib import Path

from app.schemas.rules import RetrievedChunk
from scripts.run_rag_eval import RagCase, evaluate, load_cases, render_markdown


class StubRepository:
    def search(self, question: str, *, mode: str, top_k: int = 5) -> list[RetrievedChunk]:
        if "unknown" in question:
            return []
        return [
            RetrievedChunk(
                chunk_id="b-1",
                content="Safety car procedure.",
                document_title="FIA Regulations Section B",
                section="Section B",
            )
        ][:top_k]


def test_load_cases_reads_jsonl(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        '{"name":"safety","question":"safety car","expected_sections":["Section B"]}\n',
        encoding="utf-8",
    )

    cases = load_cases(cases_path)

    assert cases == [RagCase("safety", "safety car", ["Section B"])]


def test_evaluate_reports_recall_mrr_and_negative_rejection() -> None:
    cases = [
        RagCase("positive", "safety car", ["Section B"]),
        RagCase("negative", "unknown rule", [], expect_evidence=False),
    ]

    metrics, results = evaluate(StubRepository(), cases, top_k=5)  # type: ignore[arg-type]

    assert metrics["recall_at_1"] == 1.0
    assert metrics["recall_at_5"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["strong_evidence_rejection_rate"] == 1.0
    assert all(result.passed for result in results)
    assert "Recall@5: 100.00%" in render_markdown(metrics, results)


def test_evaluate_requires_clause_or_accepted_chunk_when_annotated() -> None:
    cases = [
        RagCase(
            "clause",
            "safety car",
            ["Section B"],
            expected_articles=["B55"],
            accepted_chunk_ids=["b-accepted"],
        )
    ]

    metrics, results = evaluate(StubRepository(), cases, top_k=5)  # type: ignore[arg-type]

    assert metrics["section_recall_at_5"] == 1.0
    assert metrics["clause_hit_rate"] == 0.0
    assert metrics["recall_at_5"] == 0.0
    assert results[0].passed is False
