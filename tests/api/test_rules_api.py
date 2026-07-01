from fastapi.testclient import TestClient

from app.main import app
from app.schemas.rules import Citation, RetrievalDebugResponse, RetrievedChunk, RuleAskResponse


class StubQAService:
    def ask(self, request) -> RuleAskResponse:
        return RuleAskResponse(
            answer=f"stub answer for: {request.question}",
            citations=[
                Citation(
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting] - Iss 07 - 2026-06-25",
                    article="(4)",
                    section=None,
                    page=9,
                    excerpt="Unsafe release occurs when a car is released in an unsafe condition.",
                )
            ],
            retrieved_chunks=[
                RetrievedChunk(
                    chunk_id="chunk-unsafe-release",
                    content="Unsafe release occurs when a car is released in an unsafe condition.",
                    score=12.0,
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting] - Iss 07 - 2026-06-25",
                    article="(4)",
                    page=9,
                )
            ],
        )

    def debug_retrieval(self, request) -> RetrievalDebugResponse:
        return RetrievalDebugResponse(
            question=request.question,
            normalized_question=f"{request.question} red flag",
            rewritten_queries=["What is a red flag in Formula 1 regulations?"],
            retrieval_queries=[
                f"{request.question} red flag",
                "What is a red flag in Formula 1 regulations?",
            ],
            extracted_phrases=["red flag"],
            expanded_keywords=["red", "flag", "suspension", "stopped"],
            preferred_sections=["Section B"],
            retrieved_chunks=[
                RetrievedChunk(
                    chunk_id="chunk-red-flag",
                    content="If the race is suspended, red flags will be shown at all marshal posts.",
                    score=15.0,
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting] - Iss 07 - 2026-06-25",
                    article="(4)",
                    page=12,
                )
            ],
        )


def test_rules_ask_returns_grounded_response(monkeypatch) -> None:
    from app.api import rules

    monkeypatch.setattr(rules, "qa_service", StubQAService())
    client = TestClient(app)

    response = client.post(
        "/api/rules/ask",
        json={"question": "What is an unsafe release?"},
    )

    assert response.status_code == 200

    body = response.json()
    assert body["answer"] == "stub answer for: What is an unsafe release?"
    assert len(body["citations"]) == 1
    assert body["citations"][0]["page"] == 9
    assert len(body["retrieved_chunks"]) == 1
    assert body["retrieved_chunks"][0]["score"] == 12.0


def test_rules_retrieval_debug_returns_debug_payload(monkeypatch) -> None:
    from app.api import rules

    monkeypatch.setattr(rules, "qa_service", StubQAService())
    client = TestClient(app)

    response = client.post(
        "/api/rules/retrieve/debug",
        json={"question": "红旗是什么？"},
    )

    assert response.status_code == 200

    body = response.json()
    assert body["normalized_question"].endswith("red flag")
    assert body["rewritten_queries"] == ["What is a red flag in Formula 1 regulations?"]
    assert body["preferred_sections"] == ["Section B"]
    assert len(body["retrieved_chunks"]) == 1
    assert body["retrieved_chunks"][0]["score"] == 15.0


def test_rules_ask_rejects_empty_question() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/rules/ask",
        json={"question": ""},
    )

    assert response.status_code == 422
