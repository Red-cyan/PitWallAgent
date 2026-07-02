from app.schemas.agent import AgentQueryResponse
from app.services.agent_service import AgentService


class StubIntentRouter:
    def route(self, message: str, fallback_intent: str | None = None) -> str:
        if "红旗" in message:
            return "regulation"
        if "积分榜" in message:
            return "race"
        if fallback_intent is not None:
            return fallback_intent
        return "general"

    def looks_like_follow_up(self, message: str) -> bool:
        return message.strip() in {"那呢？", "然后呢？"}


class StubPlanner:
    def plan(self, message: str, fallback_intent: str | None = None) -> dict:
        if "积分榜" in message:
            return {
                "intent": "race",
                "tool_name": "race_tool",
                "action": "get_driver_standings",
                "params": {},
            }
        return {
            "intent": "general",
            "tool_name": "general_tool",
            "action": "answer",
            "params": {"question": message},
        }


class StubToolDispatcher:
    def execute_plan(self, plan: dict):
        class Result:
            def __init__(self, tool_name: str, success: bool, payload: dict, error: str | None = None) -> None:
                self.tool_name = tool_name
                self.success = success
                self.payload = payload
                self.error = error

        if plan["intent"] == "race":
            return Result(
                tool_name="race_tool",
                success=True,
                payload={
                    "action": "get_driver_standings",
                    "standings": [
                        {"position": 1, "driver_name": "Andrea Kimi Antonelli", "team_name": "Mercedes", "points": 171},
                        {"position": 2, "driver_name": "George Russell", "team_name": "Mercedes", "points": 131},
                    ],
                },
            )

        return Result(
            tool_name="general_tool",
            success=True,
            payload={"response": {"answer": "你好，我是 PitWall。", "mode": "llm"}},
        )


class StubRuntime:
    def run(
        self,
        message: str,
        fallback_intent: str | None = None,
    ) -> AgentQueryResponse:
        return AgentQueryResponse(
            intent="regulation",
            tool_name="regulation_tool",
            success=True,
            final_answer="graph answer",
            result={"message": message, "mode": "graph"},
            error=None,
        )


def test_agent_service_routes_and_dispatches_without_runtime() -> None:
    service = AgentService(
        intent_router=StubIntentRouter(),
        planner=StubPlanner(),
        tool_dispatcher=StubToolDispatcher(),
        runtime=None,
    )
    service.runtime = None

    response = service.handle_query("车手积分榜第二名是谁？")

    assert response.intent == "race"
    assert response.tool_name == "race_tool"
    assert response.success is True
    assert "George Russell" in response.final_answer
    assert "第 2 名" in response.final_answer


def test_agent_service_supports_general_answers_without_runtime() -> None:
    service = AgentService(
        intent_router=StubIntentRouter(),
        planner=StubPlanner(),
        tool_dispatcher=StubToolDispatcher(),
        runtime=None,
    )
    service.runtime = None

    response = service.handle_query("你好")

    assert response.intent == "general"
    assert response.tool_name == "general_tool"
    assert response.final_answer == "你好，我是 PitWall。"


def test_agent_service_uses_runtime_when_provided() -> None:
    service = AgentService(
        intent_router=StubIntentRouter(),
        planner=StubPlanner(),
        tool_dispatcher=StubToolDispatcher(),
        runtime=StubRuntime(),
    )

    response = service.handle_query("红旗是什么？")

    assert response.intent == "regulation"
    assert response.result["mode"] == "graph"
    assert response.final_answer == "graph answer"
