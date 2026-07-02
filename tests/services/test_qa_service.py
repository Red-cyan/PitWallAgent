from app.schemas.rules import RetrievedChunk, RuleAskRequest
from app.services.qa_service import RegulationQAService


class StubRepository:
    def search_relevant_chunks(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id="chunk-1",
                content="Unsafe release occurs when a car is released in a way that endangers pit lane personnel or another driver.",
                score=12.0,
                document_title="FIA 2026 F1 Regulations - Section B [Sporting] - Iss 07 - 2026-06-25",
                article="(4)",
                page=9,
            )
        ]


class StubLLMClient:
    def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        return "这是基于检索片段生成的测试回答。"


def test_qa_service_returns_llm_answer() -> None:
    service = RegulationQAService(
        repository=StubRepository(),
        llm_client=StubLLMClient(),
    )

    response = service.ask(RuleAskRequest(question="What is an unsafe release?"))

    assert response.answer == "这是基于检索片段生成的测试回答。"
    assert len(response.citations) == 1
    assert response.citations[0].page == 9
    assert response.retrieved_chunks[0].document_title.startswith("FIA 2026 F1 Regulations")
    assert response.answer_status == "answered"
    assert response.evidence_count == 1


def test_qa_service_falls_back_when_no_chunks() -> None:
    class EmptyRepository:
        def search_relevant_chunks(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
            return []

    service = RegulationQAService(
        repository=EmptyRepository(),
        llm_client=StubLLMClient(),
    )

    response = service.ask(RuleAskRequest(question="What is parc ferme?"))

    assert "未检索到" in response.answer
    assert "避免编造规则" in response.answer
    assert response.citations == []
    assert response.retrieved_chunks == []
    assert response.answer_status == "insufficient_evidence"
    assert response.confidence == "low"
