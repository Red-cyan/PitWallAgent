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


class RegulationPlanner:
    def plan(self, message: str, fallback_intent: str | None = None) -> dict:
        return {
            "intent": "regulation",
            "tool_name": "regulation_tool",
            "action": "ask",
            "params": {"question": message},
        }


class InsufficientEvidenceDispatcher:
    """首次返回 insufficient_evidence，重规划后返回完整答案。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build_plan(self, intent: str, message: str) -> dict:
        return {"intent": intent, "tool_name": "dispatcher", "action": "unsupported", "params": {}}

    def execute_plan(self, plan: dict) -> ToolResult:
        self.calls.append(plan)
        if len(self.calls) == 1:
            return ToolResult(
                tool_name="regulation_tool",
                success=True,
                payload={"response": {"answer_status": "insufficient_evidence", "mode": "offline", "answer": ""}},
            )
        return ToolResult(
            tool_name="regulation_tool",
            success=True,
            payload={"response": {"answer_status": "answered", "mode": "llm", "answer": "规则 X 不允许。"}},
        )


class EmptyNewsDispatcher:
    """首次返回空文章列表，重规划后返回新闻。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build_plan(self, intent: str, message: str) -> dict:
        return {"intent": intent, "tool_name": "dispatcher", "action": "unsupported", "params": {}}

    def execute_plan(self, plan: dict) -> ToolResult:
        self.calls.append(plan)
        if len(self.calls) == 1:
            return ToolResult(tool_name="news_tool", success=True, payload={"articles": []})
        return ToolResult(
            tool_name="news_tool",
            success=True,
            payload={"articles": [{"title": "Headline 1"}]},
        )


def test_insufficient_evidence_triggers_replanning() -> None:
    dispatcher = InsufficientEvidenceDispatcher()
    reflector = StubReflector(
        [
            {
                "finish": False,
                "reason": "evidence missing, re-ask with different query",
                "next_plan": {
                    "tool_name": "regulation_tool",
                    "action": "ask",
                    "params": {"question": "换个问法"},
                },
            }
        ]
    )
    runtime = LangGraphAgentRuntime(
        planner=cast_any(RegulationPlanner()),
        tool_dispatcher=dispatcher,  # type: ignore[arg-type]
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
    )

    response = runtime.run("排位赛有什么规则？")

    assert len(dispatcher.calls) == 2
    assert dispatcher.calls[1]["params"]["question"] == "换个问法"
    assert response.success is True
    assert "规则 X 不允许。" in response.final_answer
    assert response.trace["judge_outcomes"] == [
        "evidence missing, re-ask with different query",
        "no_judge_needed",
    ]


def test_empty_news_result_triggers_replanning() -> None:
    dispatcher = EmptyNewsDispatcher()
    reflector = StubReflector(
        [
            {
                "finish": False,
                "reason": "no articles found, list recent instead",
                "next_plan": {
                    "tool_name": "news_tool",
                    "action": "list_recent",
                    "params": {"limit": 5},
                },
            }
        ]
    )
    runtime = LangGraphAgentRuntime(
        planner=cast_any(SuccessPlanner()),
        tool_dispatcher=dispatcher,  # type: ignore[arg-type]
        reflector=reflector,  # type: ignore[arg-type]
        checkpointer=None,
    )

    response = runtime.run("诺里斯有什么新闻")

    assert len(dispatcher.calls) == 2
    assert dispatcher.calls[0]["action"] == "list_recent"
    assert dispatcher.calls[1]["action"] == "list_recent"
    assert "Headline 1" in response.final_answer


def test_insufficient_evidence_without_llm_stays_deterministic() -> None:
    dispatcher = InsufficientEvidenceDispatcher()

    class DisabledReflector(StubReflector):
        @property
        def enabled(self) -> bool:
            return False

    runtime = LangGraphAgentRuntime(
        planner=cast_any(RegulationPlanner()),
        tool_dispatcher=dispatcher,  # type: ignore[arg-type]
        reflector=cast_any(DisabledReflector([])),
        checkpointer=None,
    )

    response = runtime.run("排位赛有什么规则？")

    # 无 LLM 时保持确定性：只执行一次，不进入重规划
    assert len(dispatcher.calls) == 1
    assert response.trace["judge_outcome"] == "judge_disabled"


def test_reflector_builds_structured_observation_summary() -> None:
    reflector = ReActReflector()

    messages = reflector._build_messages(
        message="排位赛有什么规则？",
        intent="regulation",
        tool_plan={"intent": "regulation", "tool_name": "regulation_tool", "action": "ask", "params": {"question": "排位赛有什么规则？"}},
        tool_result=ToolResult(
            tool_name="regulation_tool",
            success=True,
            payload={"response": {"answer_status": "insufficient_evidence", "evidence_count": 0}},
        ),
    )

    content = messages[1]["content"]
    assert "answer_status" in content
    assert "insufficient_evidence" in content
    assert "Tool output summary" in content


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
