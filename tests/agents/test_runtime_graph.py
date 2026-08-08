from typing import Any, cast

from app.agents.runtime_graph import LangGraphAgentRuntime
from app.tools.base import ToolResult


class StubPlanner:
    def plan(self, message: str, fallback_intent: str | None = None) -> dict:
        if "积分榜" in message:
            return {
                "intent": "race",
                "tool_name": "race_tool",
                "action": "get_driver_standings",
                "params": {},
            }
        if "你好" in message:
            return {
                "intent": "general",
                "tool_name": "general_tool",
                "action": "answer",
                "params": {"question": message},
            }
        return {
            "intent": "news",
            "tool_name": "news_tool",
            "action": "list_recent",
            "params": {"limit": 5},
        }


class StubToolDispatcher:
    def build_plan(self, intent: str, message: str) -> dict:
        return {"intent": intent, "tool_name": "dispatcher", "action": "unsupported", "params": {}}

    def execute_plan(self, plan: dict):
        class Result:
            tool_name = plan["tool_name"]
            success = True
            payload = (
                {
                    "action": "get_driver_standings",
                    "standings": [
                        {"position": 1, "driver_name": "Andrea Kimi Antonelli", "team_name": "Mercedes", "points": 171},
                        {"position": 2, "driver_name": "George Russell", "team_name": "Mercedes", "points": 131},
                    ],
                }
                if plan["tool_name"] == "race_tool"
                else {
                    "action": "answer",
                    "response": {"answer": "你好，我是 PitWall。", "mode": "llm"},
                }
                if plan["tool_name"] == "general_tool"
                else {
                    "articles": [
                        {"title": "Headline 1"},
                        {"title": "Headline 2"},
                    ]
                }
            )
            error = None

        return Result()


def test_langgraph_runtime_runs_end_to_end() -> None:
    runtime = LangGraphAgentRuntime(
        planner=cast(Any, StubPlanner()),
        tool_dispatcher=cast(Any, StubToolDispatcher()),
    )

    response = runtime.run("今天有什么新闻？")

    assert response.intent == "news"
    assert response.tool_name == "news_tool"
    assert response.success is True
    assert response.result["tool_plan"]["action"] == "list_recent"
    assert response.trace["action"] == "list_recent"
    assert response.trace["intent"] == "news"
    assert "Headline 1" in response.final_answer


def test_langgraph_runtime_formats_requested_race_position() -> None:
    runtime = LangGraphAgentRuntime(
        planner=cast(Any, StubPlanner()),
        tool_dispatcher=cast(Any, StubToolDispatcher()),
    )

    response = runtime.run("车手积分榜第二名是谁？")

    assert response.intent == "race"
    assert response.tool_name == "race_tool"
    assert response.success is True
    assert "George Russell" in response.final_answer
    assert "第 2 名" in response.final_answer


def test_langgraph_runtime_supports_general_answers() -> None:
    runtime = LangGraphAgentRuntime(
        planner=cast(Any, StubPlanner()),
        tool_dispatcher=cast(Any, StubToolDispatcher()),
    )

    response = runtime.run("你好")

    assert response.intent == "general"
    assert response.tool_name == "general_tool"
    assert response.final_answer == "你好，我是 PitWall。"


class MultiStepPlanner:
    def plan(self, message: str, fallback_intent: str | None = None) -> dict:
        return {
            "intent": "news",
            "tool_name": "news_tool",
            "action": "search",
            "params": {"query": "norris", "limit": 5},
            "steps": [
                {
                    "intent": "news",
                    "tool_name": "news_tool",
                    "action": "search",
                    "params": {"query": "norris", "limit": 5},
                    "output_key": "news_hit",
                },
                {
                    "intent": "regulation",
                    "tool_name": "regulation_tool",
                    "action": "ask",
                    "params": {"question": "$ref:news_hit.articles.0.title"},
                    "output_key": "rule_check",
                },
            ],
        }


class RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build_plan(self, intent: str, message: str) -> dict:
        return {"intent": intent, "tool_name": "dispatcher", "action": "unsupported", "params": {}}

    def execute_plan(self, plan: dict) -> ToolResult:
        self.calls.append(plan)
        if plan["action"] == "search":
            return ToolResult(
                tool_name="news_tool",
                success=True,
                payload={"articles": [{"title": "Norris penalised in China GP"}]},
            )
        return ToolResult(
            tool_name="regulation_tool",
            success=True,
            payload={"response": {"answer": "对应规则是 X。", "mode": "llm", "answer_status": "answered"}},
        )


def test_runtime_executes_multi_step_plan_in_order_with_ref_interpolation() -> None:
    dispatcher = RecordingDispatcher()
    runtime = LangGraphAgentRuntime(
        planner=cast(Any, MultiStepPlanner()),
        tool_dispatcher=cast(Any, dispatcher),
        checkpointer=None,
    )

    response = runtime.run("诺里斯最近的新闻，他违反了哪条规则")

    # 两步都执行了，且按序
    assert [call["action"] for call in dispatcher.calls] == ["search", "ask"]
    # 第二步的 $ref 引用被第一步输出插值
    assert dispatcher.calls[1]["params"]["question"] == "Norris penalised in China GP"
    assert response.success is True
    assert "对应规则是 X。" in response.final_answer
    # trace 暴露计划序列与执行序列
    assert [step["output_key"] for step in response.trace["plan"]] == ["news_hit", "rule_check"]
    assert [step["action"] for step in response.trace["steps"]] == ["search", "ask"]
    assert "continue_plan" in response.trace["judge_outcomes"]


def test_runtime_single_step_plan_has_plan_trace() -> None:
    runtime = LangGraphAgentRuntime(
        planner=cast(Any, StubPlanner()),
        tool_dispatcher=cast(Any, StubToolDispatcher()),
        checkpointer=None,
    )

    response = runtime.run("今天有什么新闻？")

    assert [step["output_key"] for step in response.trace["plan"]] == ["step_0"]
    assert len(response.trace["steps"]) == 1


class ArticlePlanner:
    def plan(self, message: str, fallback_intent: str | None = None) -> dict:
        return {
            "intent": "news",
            "tool_name": "news_tool",
            "action": "get_article",
            "params": {"article_id": 42},
        }


class ArticleDispatcher:
    def build_plan(self, intent: str, message: str) -> dict:
        return {"intent": intent, "tool_name": "dispatcher", "action": "unsupported", "params": {}}

    def execute_plan(self, plan: dict) -> ToolResult:
        return ToolResult(
            tool_name="news_tool",
            success=True,
            payload={"article": {"title": "Article 42", "summary": "McLaren floor upgrade."}},
        )


class CountingReflector:
    def __init__(self) -> None:
        self.judge_calls = 0

    @property
    def enabled(self) -> bool:
        return True

    def judge(self, **kwargs: Any) -> dict:
        self.judge_calls += 1
        return {"finish": True, "reason": "complete", "next_plan": None}


def test_get_article_success_does_not_trigger_judge() -> None:
    reflector = CountingReflector()
    runtime = LangGraphAgentRuntime(
        planner=cast(Any, ArticlePlanner()),
        tool_dispatcher=cast(Any, ArticleDispatcher()),
        reflector=cast(Any, reflector),
        checkpointer=None,
    )

    response = runtime.run("看看 article 42")

    assert response.success is True
    assert reflector.judge_calls == 0
    assert response.trace["judge_outcome"] == "no_judge_needed"


class FourStepPlanner:
    def plan(self, message: str, fallback_intent: str | None = None) -> dict:
        steps = [
            {"intent": "news", "tool_name": "news_tool", "action": "search", "params": {"query": "norris", "limit": 5}, "output_key": f"step_{i}"}
            for i in range(4)
        ]
        return {**steps[0], "steps": steps}


def test_multi_step_plan_exceeds_max_steps_but_completes() -> None:
    dispatcher = RecordingDispatcher()
    runtime = LangGraphAgentRuntime(
        planner=cast(Any, FourStepPlanner()),
        tool_dispatcher=cast(Any, dispatcher),
        checkpointer=None,
        max_steps=2,
    )

    response = runtime.run("诺里斯相关新闻")

    # 计划内步骤不消耗修复轮次预算：4 步计划在 max_steps=2 下仍全部执行
    assert len(dispatcher.calls) == 4
    assert response.success is True
    assert len(response.trace["steps"]) == 4
