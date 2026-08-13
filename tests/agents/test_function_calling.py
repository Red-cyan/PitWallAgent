from types import SimpleNamespace
from typing import Any, cast

from app.agents.function_calling import FunctionCallingAgent, build_tool_functions
from app.agents.tool_dispatcher import ToolDispatcher


class StubNewsTool:
    name = "news_tool"

    def invoke(self, **kwargs):
        class Result:
            tool_name = "news_tool"
            success = True
            payload = {"articles": [{"title": "Headline 1"}]}
            error = None

        return Result()


class StubRaceTool:
    name = "race_tool"

    def invoke(self, **kwargs):
        class Result:
            tool_name = "race_tool"
            success = True
            payload = {
                "action": "get_driver_standings",
                "standings": [
                    {"position": 1, "driver_name": "Andrea Kimi Antonelli", "team_name": "Mercedes", "points": 171},
                ],
            }
            error = None

        return Result()


class FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=arguments)

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.function.name, "arguments": self.function.arguments},
        }


class FakeMessage:
    def __init__(self, content: str | None, tool_calls: list[FakeToolCall] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class StubLLMClient:
    def __init__(self, replies: list[FakeMessage], summaries: list[str | Exception] | None = None) -> None:
        self.replies = list(replies)
        self.summaries = list(summaries or [])
        self.sent_messages: list[list[dict[str, Any]]] = []
        self.summary_messages: list[list[dict[str, Any]]] = []

    def chat_tools(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], **kwargs: Any) -> FakeMessage:
        self.sent_messages.append(messages)
        return self.replies.pop(0)

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        self.summary_messages.append(messages)
        summary = self.summaries.pop(0)
        if isinstance(summary, Exception):
            raise summary
        return summary


def build_agent(llm: StubLLMClient, *, max_steps: int | None = None) -> FunctionCallingAgent:
    dispatcher = ToolDispatcher(
        news_tool=cast(Any, StubNewsTool()),
        race_tool=cast(Any, StubRaceTool()),
    )
    return FunctionCallingAgent(tool_dispatcher=dispatcher, llm_client=cast(Any, llm), max_steps=max_steps)


def test_function_calling_single_tool_loop() -> None:
    llm = StubLLMClient(
        [
            FakeMessage(
                content=None,
                tool_calls=[FakeToolCall("call_1", "list_recent", '{"limit": 5}')],
            ),
            FakeMessage(content="今天有三条 F1 新闻。"),
        ]
    )
    agent = build_agent(llm)

    response = agent.run("今天有什么新闻？")

    assert response.success is True
    assert response.final_answer == "今天有三条 F1 新闻。"
    assert response.intent == "news"
    assert response.tool_name == "news_tool"
    assert len(response.trace["steps"]) == 1
    assert response.trace["steps"][0]["action"] == "list_recent"
    assert response.trace["protocol"] == "function_calling"
    # 工具结果以 tool role 回灌
    tool_messages = [m for m in llm.sent_messages[-1] if m["role"] == "tool"]
    assert len(tool_messages) == 1
    assert "Headline 1" in tool_messages[0]["content"]


def test_function_calling_parallel_tool_calls() -> None:
    llm = StubLLMClient(
        [
            FakeMessage(
                content=None,
                tool_calls=[
                    FakeToolCall("call_1", "list_recent", '{"limit": 5}'),
                    FakeToolCall("call_2", "get_driver_standings", "{}"),
                ],
            ),
            FakeMessage(content="新闻与积分榜都已获取。"),
        ]
    )
    agent = build_agent(llm)

    response = agent.run("给我新闻和车手积分")

    assert len(response.trace["steps"]) == 2
    actions = [step["action"] for step in response.trace["steps"]]
    assert actions == ["list_recent", "get_driver_standings"]
    tool_messages = [m for m in llm.sent_messages[-1] if m["role"] == "tool"]
    assert len(tool_messages) == 2


def test_function_calling_multi_round_reasoning() -> None:
    llm = StubLLMClient(
        [
            FakeMessage(content=None, tool_calls=[FakeToolCall("call_1", "list_recent", '{"limit": 5}')]),
            FakeMessage(content=None, tool_calls=[FakeToolCall("call_2", "get_driver_standings", "{}")]),
            FakeMessage(content="最终回答。"),
        ]
    )
    agent = build_agent(llm)

    response = agent.run("先看新闻再看积分")

    assert len(response.trace["steps"]) == 2
    assert response.trace["steps"][1]["step"] == 2
    assert response.final_answer == "最终回答。"


def test_tool_functions_cover_all_actions() -> None:
    functions = build_tool_functions()

    names = {item["function"]["name"] for item in functions}
    assert names == {
        "list_recent",
        "search",
        "get_article",
        "get_insights",
        "get_rules_analysis",
        "list_schedule",
        "get_next_race",
        "get_previous_race",
        "get_race_results",
        "get_driver_standings",
        "get_constructor_standings",
        "ask",
        "analyze",
        "answer",
    }
    ask = next(item for item in functions if item["function"]["name"] == "ask")
    assert ask["function"]["parameters"]["required"] == ["question"]


def test_function_calling_empty_content_falls_back() -> None:
    llm = StubLLMClient([FakeMessage(content=None, tool_calls=None)])
    agent = build_agent(llm)

    response = agent.run("你好")

    assert response.success is True
    assert response.final_answer == "未能生成回答。"
    assert len(response.trace["steps"]) == 0


def test_function_calling_forces_summary_after_max_steps() -> None:
    llm = StubLLMClient(
        [
            FakeMessage(content=None, tool_calls=[FakeToolCall("call_1", "list_recent", '{"limit": 5}')]),
            FakeMessage(content=None, tool_calls=[FakeToolCall("call_2", "get_driver_standings", "{}")]),
        ],
        summaries=["根据已获取的资料，这是最终总结。"],
    )
    agent = build_agent(llm, max_steps=2)

    response = agent.run("先查询资料，再给出总结")

    assert response.final_answer == "根据已获取的资料，这是最终总结。"
    assert response.trace["max_steps_reached"] is True
    assert response.trace["finalization_mode"] == "forced_summary"
    assert len(llm.summary_messages) == 1
    assert "Do not call any more tools" in llm.summary_messages[0][-1]["content"]
    assert "350 Chinese characters" in llm.summary_messages[0][-1]["content"]


def test_function_calling_uses_tool_answer_when_forced_summary_fails() -> None:
    llm = StubLLMClient(
        [FakeMessage(content=None, tool_calls=[FakeToolCall("call_1", "answer", '{"question": "F1"}')])],
        summaries=[RuntimeError("summary unavailable")],
    )

    class StubGeneralTool:
        name = "general_tool"

        def invoke(self, **kwargs: Any):
            return SimpleNamespace(
                tool_name=self.name,
                success=True,
                payload={"response": {"answer": "工具已经生成的可用回答。"}},
                error=None,
            )

    dispatcher = ToolDispatcher(general_tool=cast(Any, StubGeneralTool()))
    agent = FunctionCallingAgent(tool_dispatcher=dispatcher, llm_client=cast(Any, llm), max_steps=1)

    response = agent.run("介绍 F1")

    assert response.final_answer == "工具已经生成的可用回答。"
    assert response.trace["max_steps_reached"] is True
    assert response.trace["finalization_mode"] == "tool_result_fallback"
