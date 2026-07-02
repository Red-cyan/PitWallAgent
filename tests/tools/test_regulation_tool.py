from app.schemas.rules import Citation, RetrievalDebugResponse, RetrievedChunk, RuleAskResponse
from app.tools.regulation_tool import RegulationTool


class StubQAService:
    def ask(self, request) -> RuleAskResponse:
        return RuleAskResponse(
            answer=f"stub answer for: {request.question}",
            citations=[
                Citation(
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting] - Iss 07 - 2026-06-25",
                    article="B5.14.2",
                    section=None,
                    page=47,
                    excerpt="Red flags will be shown at all marshal posts.",
                )
            ],
            retrieved_chunks=[
                RetrievedChunk(
                    chunk_id="chunk-red-flag",
                    content="Red flags will be shown at all marshal posts.",
                    score=14.0,
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting] - Iss 07 - 2026-06-25",
                    article="B5.14.2",
                    page=47,
                )
            ],
        )

    def debug_retrieval(self, request) -> RetrievalDebugResponse:
        return RetrievalDebugResponse(
            question=request.question,
            normalized_question=f"{request.question} red flag",
            rewritten_queries=["What is the red flag procedure in Formula 1?"],
            retrieval_queries=[f"{request.question} red flag"],
            extracted_phrases=["red flag"],
            expanded_keywords=["red", "flag"],
            preferred_sections=["Section B"],
            retrieved_chunks=[
                RetrievedChunk(
                    chunk_id="chunk-red-flag",
                    content="Red flags will be shown at all marshal posts.",
                    score=14.0,
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting] - Iss 07 - 2026-06-25",
                    article="B5.14.2",
                    page=47,
                )
            ],
        )


def test_regulation_tool_asks_question() -> None:
    tool = RegulationTool(qa_service=StubQAService())

    result = tool.invoke(action="ask", question="What is the red flag procedure?")

    assert result.success is True
    assert result.payload["response"]["answer"] == "stub answer for: What is the red flag procedure?"


def test_regulation_tool_returns_debug_payload() -> None:
    tool = RegulationTool(qa_service=StubQAService())

    result = tool.invoke(action="debug_retrieval", question="红旗是什么？")

    assert result.success is True
    assert result.payload["response"]["preferred_sections"] == ["Section B"]


def test_regulation_tool_rejects_missing_question() -> None:
    tool = RegulationTool(qa_service=StubQAService())

    result = tool.invoke(action="ask", question="")

    assert result.success is False
    assert result.error == "Question is required."
