from typing import Any

import pytest

from app.agents.reflector import ReActReflector
from app.agents.runtime_graph import LangGraphAgentRuntime
from app.tools.base import ToolResult


class StubPlanner:
    def plan(self, message: str, fallback_intent: str | None = None) -> dict:
        return {
            "intent": "news",
            "tool_name": "news_tool",
            "action": "get_article",
            "params": {"article_id": 999},
        }


class SuccessPlanner:
    def plan(self, message: str, fallback_intent: str | None = None) -> dict:
        return {
            "intent": "news",
            "tool_name": "news_tool",
            "action": "list_recent",
            "params": {"limit": 5},
        }


class RepairingDispatcher:
    """首次 get_article 失败，随后 list_recent 成功，用于验证失败修复循环。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build_plan(self, intent: str, message: str) -> dict:
        return {"intent": intent, "tool_name": "dispatcher", "action": "unsupported", "params": {}}

    def execute_plan(self, plan: dict) -> ToolResult:
        self.calls.append(plan)
        if plan["action"] == "get_article":
            return ToolResult(
                tool_name="news_tool",
                success=False,
                error="article 999 not found",
            )
        if plan["action"] == "list_recent":
            return ToolResult(
                tool_name="news_tool",
                success=True,
                payload={"articles": [{"title": "Headline 1"}, {"title": "Headline 2"}]},
            )
        return ToolResult(tool_name=plan.get("tool_name", "news_tool"), success=True, payload={})


class AlwaysFailingDispatcher:
    """每次执行都失败，用于验证步数上限。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build_plan(self, intent: str, message: str) -> dict:
        return {"intent": intent, "tool_name": "dispatcher", "action": "unsupported", "params": {}}

    def execute_plan(self, plan: dict) -> ToolResult:
        self.calls.append(plan)
        return ToolResult(tool_name="news_tool", success=False, error="boom")


class StubReflector:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.judge_calls: list[dict] = []

    @property
    def enabled(self) -> bool:
        return True

    def judge(self, **kwargs: Any) -> dict:
        self.judge_calls.append(kwargs)
        return self.responses.pop(0)


REPAIR_PLAN = {
    "finish": False,
    "reason": "article not found, fall back to recent",
    "next_plan": {
        "tool_name": "news_tool",
        "action": "list_recent",
        "params": {"limit": 5},
    },
}


def test_failure_repair_loops_back_and_succeeds() -> None:
    dispatcher = RepairingDispatcher()
    reflector = StubReflector([REPAIR_PLAN])
    runtime = LangGraphAgentRuntime(
        planner=cast_any(StubPlanner()),
        tool_dispatcher=dispatcher,  # type: ignore[arg-type]
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
    )

    response = runtime.run("帮我看看 article 999")

    assert response.success is True
    assert len(dispatcher.calls) == 2
    assert dispatcher.calls[0]["action"] == "get_article"
    assert dispatcher.calls[1]["action"] == "list_recent"
    assert response.trace["judge_outcomes"] == ["article not found, fall back to recent", "no_judge_needed"]
    assert response.trace["judge_outcome"] == "no_judge_needed"
    assert "Headline 1" in response.final_answer
    steps = response.trace["steps"]
    assert len(steps) == 2
    assert steps[0]["step"] == 1
    assert steps[1]["step"] == 2


def test_failure_with_give_up_returns_error_answer() -> None:
    dispatcher = AlwaysFailingDispatcher()
    reflector = StubReflector([{"finish": True, "reason": "give_up", "next_plan": None}])
    runtime = LangGraphAgentRuntime(
        planner=cast_any(StubPlanner()),
        tool_dispatcher=dispatcher,  # type: ignore[arg-type]
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
    )

    response = runtime.run("帮我看看 article 999")

    assert response.success is False
    assert response.final_answer == "boom"
    assert response.trace["judge_outcome"] == "give_up"


def test_success_skips_judge_for_news_intent() -> None:
    dispatcher = RepairingDispatcher()
    reflector = StubReflector([])
    runtime = LangGraphAgentRuntime(
        planner=cast_any(SuccessPlanner()),
        tool_dispatcher=dispatcher,  # type: ignore[arg-type]
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
    )

    response = runtime.run("给我新闻")

    assert response.success is True
    assert reflector.judge_calls == []


def test_max_steps_forces_finish() -> None:
    dispatcher = AlwaysFailingDispatcher()
    reflector = StubReflector([REPAIR_PLAN, REPAIR_PLAN])
    runtime = LangGraphAgentRuntime(
        planner=cast_any(StubPlanner()),
        tool_dispatcher=dispatcher,  # type: ignore[arg-type]
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
        max_steps=3,
    )

    response = runtime.run("帮我看看 article 999")

    assert response.success is False
    assert len(dispatcher.calls) == 3
    assert len(reflector.judge_calls) == 2
    assert response.trace["judge_outcome"] == "max_steps_reached"
    assert len(response.trace["steps"]) == 3


def test_disabled_reflector_stays_linear() -> None:
    dispatcher = RepairingDispatcher()

    class DisabledReflector(StubReflector):
        @property
        def enabled(self) -> bool:
            return False

    reflector = DisabledReflector([REPAIR_PLAN])
    runtime = LangGraphAgentRuntime(
        planner=cast_any(StubPlanner()),
        tool_dispatcher=dispatcher,  # type: ignore[arg-type]
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
    )

    response = runtime.run("帮我看看 article 999")

    assert response.success is False
    assert len(dispatcher.calls) == 1
    assert reflector.judge_calls == []
    assert response.trace["judge_outcome"] == "judge_disabled"


def test_general_success_triggers_judge_when_enabled() -> None:
    reflector = StubReflector([{"finish": True, "reason": "complete", "next_plan": None}])
    runtime = LangGraphAgentRuntime(
        planner=cast_any(SuccessPlanner()),
        tool_dispatcher=cast_any(RepairingDispatcher()),
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
    )

    class GeneralPlanner:
        def plan(self, message: str, fallback_intent: str | None = None) -> dict:
            return {
                "intent": "general",
                "tool_name": "general_tool",
                "action": "answer",
                "params": {"question": message},
            }

    runtime = LangGraphAgentRuntime(
        planner=cast_any(GeneralPlanner()),
        tool_dispatcher=cast_any(RepairingDispatcher()),
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
    )

    response = runtime.run("介绍一下 F1")

    assert response.success is True
    assert len(reflector.judge_calls) == 1
    assert response.trace["judge_outcome"] == "complete"


def test_general_success_skips_judge_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.agents.runtime_graph.settings.agent_judge_on_success_general", False)
    reflector = StubReflector([])

    class GeneralPlanner:
        def plan(self, message: str, fallback_intent: str | None = None) -> dict:
            return {
                "intent": "general",
                "tool_name": "general_tool",
                "action": "answer",
                "params": {"question": message},
            }

    runtime = LangGraphAgentRuntime(
        planner=cast_any(GeneralPlanner()),
        tool_dispatcher=cast_any(RepairingDispatcher()),
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
    )

    response = runtime.run("介绍一下 F1")

    assert response.success is True
    assert reflector.judge_calls == []


def test_on_token_is_passed_through_loop() -> None:
    received: list[Any] = []
    reflector = StubReflector([REPAIR_PLAN])

    class RecordingDispatcher(RepairingDispatcher):
        def execute_plan(self, plan: dict, on_token=None) -> ToolResult:
            received.append(on_token)
            return super().execute_plan(plan)

    runtime = LangGraphAgentRuntime(
        planner=cast_any(StubPlanner()),
        tool_dispatcher=RecordingDispatcher(),  # type: ignore[arg-type]
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
    )

    def on_token(_token: str) -> None:
        pass

    runtime.run("帮我看看 article 999", on_token=on_token)

    assert received == [on_token, on_token]


def test_reflector_normalizes_next_plan_question_param() -> None:
    reflector = ReActReflector()

    normalized = reflector._normalize_next_plan(
        {
            "tool_name": "regulation_tool",
            "action": "ask",
            "params": {},
        },
        "排位赛有什么规则？",
    )

    assert normalized == {
        "intent": "regulation",
        "tool_name": "regulation_tool",
        "action": "ask",
        "params": {"question": "排位赛有什么规则？"},
    }


def test_reflector_rejects_unknown_tool() -> None:
    reflector = ReActReflector()

    assert reflector._normalize_next_plan(
        {"tool_name": "hack_tool", "action": "ask", "params": {}},
        "test",
    ) is None


def cast_any(value: Any) -> Any:
    return value


class RaisingPlanner:
    def plan(self, message: str, fallback_intent: str | None = None) -> dict:
        raise RuntimeError("planner down")


class RaisingReflector(StubReflector):
    @property
    def enabled(self) -> bool:
        return True

    def judge(self, **kwargs: Any) -> dict:
        raise RuntimeError("llm down")


def test_planner_failure_falls_back_to_general() -> None:
    reflector = StubReflector([{"finish": True, "reason": "complete", "next_plan": None}])
    runtime = LangGraphAgentRuntime(
        planner=cast_any(RaisingPlanner()),
        tool_dispatcher=cast_any(RepairingDispatcher()),
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
    )

    response = runtime.run("随便聊聊 F1")

    assert response.intent == "general"
    assert response.tool_name == "general_tool"


def test_reflector_exception_degrades_to_finish() -> None:
    runtime = LangGraphAgentRuntime(
        planner=cast_any(StubPlanner()),
        tool_dispatcher=cast_any(AlwaysFailingDispatcher()),
        reflector=cast_any(RaisingReflector([])),
        checkpointer=None,
    )

    response = runtime.run("帮我看看 article 999")

    assert response.success is False
    assert response.trace["judge_outcome"] == "judge_error"


def test_require_raises_on_missing_key() -> None:
    runtime = LangGraphAgentRuntime(checkpointer=None)

    with pytest.raises(ValueError):
        runtime._require({"message": "x"}, "missing_key", str)


def test_build_default_checkpointer_handles_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.memory", None)
    runtime = LangGraphAgentRuntime(checkpointer=None)
    assert runtime._build_default_checkpointer() is None
