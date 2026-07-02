from app.tools.general_tool import GeneralTool


class StubGeneralAnswerService:
    def answer(self, question: str) -> dict[str, str]:
        return {"answer": f"answer:{question}", "mode": "llm"}


def test_general_tool_answers_question() -> None:
    tool = GeneralTool(general_answer_service=StubGeneralAnswerService())

    result = tool.invoke(action="answer", question="你好")

    assert result.success is True
    assert result.tool_name == "general_tool"
    assert result.payload["response"]["answer"] == "answer:你好"


def test_general_tool_requires_question() -> None:
    tool = GeneralTool(general_answer_service=StubGeneralAnswerService())

    result = tool.invoke(action="answer", question="")

    assert result.success is False
    assert result.error == "Question is required."
