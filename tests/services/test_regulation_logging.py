import json
import logging

from app.schemas.rules import RetrievalDebugResponse, RetrievedChunk, RuleAskRequest
from app.services.qa_service import RegulationQAService


class StubRepository:
    def search_relevant_chunks(self, question: str) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id="chunk-red-flag",
                content="Red flags will be shown at all marshal posts.",
                score=14.0,
                document_title="doc",
                article="B5.14.2",
                page=47,
            )
        ]

    def debug_retrieval(self, question: str) -> RetrievalDebugResponse:
        return RetrievalDebugResponse(
            question=question,
            normalized_question=question,
            rewritten_queries=[question],
            retrieval_queries=[question],
            extracted_phrases=[],
            expanded_keywords=[],
            preferred_sections=[],
            retrieved_chunks=self.search_relevant_chunks(question),
        )


class StubLLMClient:
    def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        return "stub llm answer"


class FailingLLMClient:
    def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        raise RuntimeError("llm failed")


def test_regulation_service_emits_retrieval_and_generation_logs(caplog) -> None:
    service = RegulationQAService(repository=StubRepository(), llm_client=StubLLMClient())

    with caplog.at_level(logging.INFO, logger="pitwall.regulation"):
        response = service.ask(RuleAskRequest(question="What is red flag?"))

    assert response.answer == "stub llm answer"
    payloads = [json.loads(record.message) for record in caplog.records if record.name == "pitwall.regulation"]
    assert payloads[0]["event"] == "regulation_retrieval_completed"
    assert payloads[-1]["event"] == "regulation_answer_generated"


def test_regulation_service_emits_fallback_log_when_llm_fails(caplog) -> None:
    service = RegulationQAService(repository=StubRepository(), llm_client=FailingLLMClient())

    with caplog.at_level(logging.INFO, logger="pitwall.regulation"):
        response = service.ask(RuleAskRequest(question="What is red flag?"))

    assert "doc" in response.answer
    payloads = [json.loads(record.message) for record in caplog.records if record.name == "pitwall.regulation"]
    assert payloads[-1]["event"] == "regulation_answer_fallback_used"
    assert payloads[-1]["reason"] == "llm_error"
