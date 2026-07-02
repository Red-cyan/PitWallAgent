from app.agents.intent_router import IntentRouter
from app.agents.response_formatter import AgentResponseFormatter
from app.agents.tool_dispatcher import ToolDispatcher


class StubStrategyTool:
    name = "strategy_tool"

    def invoke(self, **kwargs):
        class Result:
            tool_name = "strategy_tool"
            success = True
            payload = {
                "action": "analyze",
                "response": {
                    "question": kwargs["question"],
                    "recommendation": "建议在安全车窗口内进站",
                    "confidence": "medium",
                    "facts": ["当前窗口损失较低"],
                    "analysis": ["安全车阶段可减少进站损失"],
                    "assumptions": ["当前轮胎已经进入衰减阶段"],
                    "cautions": ["若前方车流过密可能丢失位置"],
                },
            }
            error = None

        return Result()


class StubNewsTool:
    name = "news_tool"

    def invoke(self, **kwargs):
        raise AssertionError("not used")


class StubRaceTool:
    name = "race_tool"

    def invoke(self, **kwargs):
        raise AssertionError("not used")


class StubRegulationTool:
    name = "regulation_tool"

    def invoke(self, **kwargs):
        raise AssertionError("not used")


def test_intent_router_routes_strategy_queries() -> None:
    router = IntentRouter()

    assert router.route("Should Ferrari pit under safety car?") == "strategy"
    assert router.route("现在该不该进站？") == "strategy"


def test_tool_dispatcher_builds_strategy_plan() -> None:
    dispatcher = ToolDispatcher(
        news_tool=StubNewsTool(),
        race_tool=StubRaceTool(),
        regulation_tool=StubRegulationTool(),
        strategy_tool=StubStrategyTool(),
    )

    plan = dispatcher.build_plan(intent="strategy", message="Should Ferrari pit under safety car?")

    assert plan["tool_name"] == "strategy_tool"
    assert plan["action"] == "analyze"


def test_response_formatter_formats_strategy_answer() -> None:
    formatter = AgentResponseFormatter()

    answer = formatter.build(
        message="Should Ferrari pit under safety car?",
        intent="strategy",
        tool_name="strategy_tool",
        success=True,
        result={
            "response": {
                "recommendation": "建议在安全车窗口内进站",
                "confidence": "medium",
                "analysis": ["安全车阶段可减少进站损失"],
            }
        },
        error=None,
    )

    assert "策略建议" in answer
    assert "建议在安全车窗口内进站" in answer
