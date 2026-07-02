from app.agents.runtime_graph import LangGraphAgentRuntime


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
        planner=StubPlanner(),
        tool_dispatcher=StubToolDispatcher(),
    )

    response = runtime.run("今天有什么新闻？")

    assert response.intent == "news"
    assert response.tool_name == "news_tool"
    assert response.success is True
    assert response.result["tool_plan"]["action"] == "list_recent"
    assert response.final_answer.startswith("已获取最近的 F1 新闻")


def test_langgraph_runtime_formats_requested_race_position() -> None:
    runtime = LangGraphAgentRuntime(
        planner=StubPlanner(),
        tool_dispatcher=StubToolDispatcher(),
    )

    response = runtime.run("车手积分榜第二名是谁？")

    assert response.intent == "race"
    assert response.tool_name == "race_tool"
    assert response.success is True
    assert "George Russell" in response.final_answer
    assert "第 2 名" in response.final_answer


def test_langgraph_runtime_supports_general_answers() -> None:
    runtime = LangGraphAgentRuntime(
        planner=StubPlanner(),
        tool_dispatcher=StubToolDispatcher(),
    )

    response = runtime.run("你好")

    assert response.intent == "general"
    assert response.tool_name == "general_tool"
    assert response.final_answer == "你好，我是 PitWall。"
