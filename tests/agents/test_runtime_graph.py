from app.agents.runtime_graph import LangGraphAgentRuntime


class StubIntentRouter:
    def route(self, message: str) -> str:
        return "news"


class StubToolDispatcher:
    def build_plan(self, intent: str, message: str) -> dict:
        return {
            "tool_name": "news_tool",
            "action": "list_recent",
            "params": {"limit": 5},
        }

    def execute_plan(self, plan: dict):
        class Result:
            tool_name = "news_tool"
            success = True
            payload = {
                "articles": [
                    {"title": "Headline 1"},
                    {"title": "Headline 2"},
                ]
            }
            error = None

        return Result()


def test_langgraph_runtime_runs_end_to_end() -> None:
    runtime = LangGraphAgentRuntime(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
    )

    response = runtime.run("今天有什么新闻？")

    assert response.intent == "news"
    assert response.tool_name == "news_tool"
    assert response.success is True
    assert response.result["tool_plan"]["action"] == "list_recent"
    assert response.final_answer.startswith("已获取最近的 F1 新闻")
