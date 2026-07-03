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


def test_qa_service_section_overview_uses_requested_section() -> None:
    service = RegulationQAService(llm_client=StubLLMClient())

    response = service.ask(RuleAskRequest(question="SectionA讲了什么内容"))

    assert response.answer_status == "answered"
    assert response.query_type == "section_overview"
    assert response.source_mode == "regulation_overview"
    assert "Section A" in response.answer
    assert "General Provisions" in response.answer
    assert response.retrieved_chunks
    assert all("Section A" in chunk.document_title for chunk in response.retrieved_chunks)


def test_qa_service_document_overview_summarizes_sections() -> None:
    service = RegulationQAService(llm_client=StubLLMClient())

    response = service.ask(RuleAskRequest(question="F1的大体规则是什么样的"))

    assert response.answer_status == "answered"
    assert response.query_type == "document_overview"
    assert response.source_mode == "regulation_overview"
    assert "Section A-F" in response.answer
    assert "Section C" in response.answer
    assert response.evidence_count >= 6


def test_qa_service_returns_partial_evidence_for_weak_chunks() -> None:
    class WeakRepository:
        def search_relevant_chunks(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
            return [
                RetrievedChunk(
                    chunk_id="weak-1",
                    content="The stewards may investigate driving incidents.",
                    score=1.2,
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting]",
                    article="B14",
                    section="Section B",
                    page=42,
                    score_components={"evidence_strength": 0.0},
                )
            ]

    service = RegulationQAService(repository=WeakRepository(), llm_client=StubLLMClient())

    response = service.ask(RuleAskRequest(question="阻挡其他车手会怎样"))

    assert response.answer_status == "partial_evidence"
    assert response.confidence == "low"
    assert response.evidence_count == 1
    assert "可能相关" in response.answer
