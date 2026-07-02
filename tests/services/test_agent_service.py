from app.schemas.agent import AgentQueryResponse
from app.services.agent_service import AgentService


class StubIntentRouter:
    def route(self, message: str) -> str:
        if "红旗" in message:
            return "regulation"
        if "积分榜" in message:
            return "race"
        return "news"


class StubToolDispatcher:
    def dispatch(self, intent: str, message: str):
        class Result:
            def __init__(self, tool_name: str, success: bool, payload: dict, error: str | None = None) -> None:
                self.tool_name = tool_name
                self.success = success
                self.payload = payload
                self.error = error

        return Result(
            tool_name=f"{intent}_tool",
            success=True,
            payload={"message": message, "intent": intent},
        )


class StubRuntime:
    def run(self, message: str) -> AgentQueryResponse:
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
        tool_dispatcher=StubToolDispatcher(),
        runtime=None,
    )
    service.runtime = None

    response = service.handle_query("红旗是什么？")

    assert response.intent == "regulation"
    assert response.tool_name == "regulation_tool"
    assert response.success is True
    assert response.result["message"] == "红旗是什么？"
    assert response.final_answer == "已完成规则查询。"


def test_agent_service_uses_runtime_when_provided() -> None:
    service = AgentService(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        runtime=StubRuntime(),
    )

    response = service.handle_query("红旗是什么？")

    assert response.intent == "regulation"
    assert response.result["mode"] == "graph"
    assert response.final_answer == "graph answer"
