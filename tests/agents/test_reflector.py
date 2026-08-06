import json
from typing import Any

import pytest

from app.agents.reflector import ReActReflector
from app.tools.base import ToolResult


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.messages: list[Any] = []

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        self.messages.append(messages)
        return self.responses.pop(0)


def _tool_result(success: bool = True, error: str | None = None) -> ToolResult:
    return ToolResult(
        tool_name="news_tool",
        success=success,
        payload={"articles": [{"title": "Headline"}]} if success else {},
        error=error,
    )


def test_judge_returns_finish_from_llm() -> None:
    reflector = ReActReflector(llm_client=FakeLLM([json.dumps({"finish": True, "reason": "complete", "next_plan": None})]))

    judgement = reflector.judge(
        message="有新闻吗",
        intent="news",
        tool_plan={"tool_name": "news_tool", "action": "list_recent"},
        tool_result=_tool_result(),
        step_count=1,
        max_steps=3,
    )

    assert judgement == {"finish": True, "reason": "complete", "next_plan": None}


def test_judge_returns_next_plan_from_llm() -> None:
    reflector = ReActReflector(
        llm_client=FakeLLM(
            [
                json.dumps(
                    {
                        "finish": False,
                        "reason": "retry with fallback",
                        "next_plan": {"tool_name": "news_tool", "action": "list_recent", "params": {"limit": 5}},
                    }
                )
            ]
        )
    )

    judgement = reflector.judge(
        message="看看新闻",
        intent="news",
        tool_plan={"tool_name": "news_tool", "action": "get_article", "params": {"article_id": 9}},
        tool_result=_tool_result(success=False, error="not found"),
        step_count=1,
        max_steps=3,
    )

    assert judgement["finish"] is False
    assert judgement["next_plan"]["action"] == "list_recent"
    assert judgement["next_plan"]["params"]["limit"] == 5
    assert "news_tool" in reflector._build_messages(
        message="看看新闻",
        intent="news",
        tool_plan={"tool_name": "news_tool", "action": "get_article"},
        tool_result=_tool_result(),
    )[0]["content"]


def test_judge_falls_back_on_malformed_json() -> None:
    reflector = ReActReflector(llm_client=FakeLLM(["not json"]))

    judgement = reflector.judge(
        message="有新闻吗",
        intent="news",
        tool_plan={},
        tool_result=_tool_result(),
        step_count=1,
        max_steps=3,
    )

    assert judgement == {"finish": True, "reason": "judge_error", "next_plan": None}


def test_judge_respects_disabled_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.agents.reflector.settings.agent_judge_enabled", False)
    reflector = ReActReflector(llm_client=FakeLLM([]))

    judgement = reflector.judge(
        message="有新闻吗",
        intent="news",
        tool_plan={},
        tool_result=_tool_result(),
        step_count=1,
        max_steps=3,
    )

    assert judgement["reason"] == "judge_disabled"


def test_judge_enabled_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.agents.reflector.settings.agent_judge_enabled", True)
    monkeypatch.setattr("app.agents.reflector.settings.llm_api_key", None)
    reflector = ReActReflector()
    assert reflector.enabled is False


def test_judge_enabled_with_injected_client() -> None:
    assert ReActReflector(llm_client=FakeLLM([])).enabled is True


def test_judge_respects_max_steps() -> None:
    reflector = ReActReflector(llm_client=FakeLLM([]))

    judgement = reflector.judge(
        message="有新闻吗",
        intent="news",
        tool_plan={},
        tool_result=_tool_result(success=False),
        step_count=3,
        max_steps=3,
    )

    assert judgement["reason"] == "max_steps_reached"


def test_parse_finish_non_bool_coerced() -> None:
    reflector = ReActReflector()
    parsed = reflector._parse_and_normalize('{"finish": "yes", "reason": "x", "next_plan": null}', "hi")
    assert parsed["finish"] is True


def test_parse_invalid_next_plan_returns_finish() -> None:
    reflector = ReActReflector()
    parsed = reflector._parse_and_normalize(
        '{"finish": false, "reason": "x", "next_plan": {"tool_name": "hack_tool", "action": "ask"}}',
        "hi",
    )
    assert parsed["finish"] is True
    assert parsed["reason"] == "invalid_next_plan"


def test_normalize_rejects_non_dict_plan() -> None:
    assert ReActReflector()._normalize_next_plan("nope", "hi") is None


def test_normalize_rejects_unknown_action() -> None:
    assert (
        ReActReflector()._normalize_next_plan(
            {"tool_name": "news_tool", "action": "destroy", "params": {}},
            "hi",
        )
        is None
    )


def test_normalize_rejects_invalid_article_id() -> None:
    assert (
        ReActReflector()._normalize_next_plan(
            {"tool_name": "news_tool", "action": "get_article", "params": {"article_id": "abc"}},
            "hi",
        )
        is None
    )


def test_normalize_accepts_general_with_question() -> None:
    normalized = ReActReflector()._normalize_next_plan(
        {"tool_name": "general_tool", "action": "answer", "params": {}},
        "介绍一下 F1",
    )
    assert normalized["params"] == {"question": "介绍一下 F1"}


def test_extract_json_object_rejects_non_dict() -> None:
    with pytest.raises(ValueError):
        ReActReflector()._extract_json_object("[1, 2, 3]")
