from typing import Any, cast

from app.services.general_answer_service import GeneralAnswerService


class FailingIfCalledLLMClient:
    def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        raise AssertionError("LLM should not be called for authoritative-data questions.")


class StubLLMClient:
    def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        return "塞纳是 F1 历史上最具代表性的车手之一。"


def test_general_answer_refuses_to_guess_authoritative_data() -> None:
    service = GeneralAnswerService(llm_client=cast(Any, FailingIfCalledLLMClient()))

    response = service.answer("现在 F1 车手积分榜第一是谁？")

    assert response["mode"] == "needs_grounded_tool"
    assert response["answer_status"] == "insufficient_evidence"
    assert "不能只凭通用模型知识猜测" in str(response["answer"])


def test_general_answer_allows_stable_open_ended_questions() -> None:
    service = GeneralAnswerService(llm_client=cast(Any, StubLLMClient()))

    response = service.answer("塞纳为什么被认为很伟大？")

    assert response["mode"] == "llm"
    assert response["answer_status"] == "answered"
    assert "塞纳" in str(response["answer"])


def test_general_answer_fallback_when_llm_fails() -> None:
    class FailingLLMClient:
        def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
            raise RuntimeError("boom")

    service = GeneralAnswerService(llm_client=cast(Any, FailingLLMClient()))

    response = service.answer("介绍一下 F1 空气动力学")

    assert response["mode"] == "fallback"
    assert response["answer_status"] == "insufficient_evidence"
