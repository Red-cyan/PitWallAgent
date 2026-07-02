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


def test_agent_service_routes_and_dispatches() -> None:
    service = AgentService(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
    )

    response = service.handle_query("红旗是什么？")

    assert response.intent == "regulation"
    assert response.tool_name == "regulation_tool"
    assert response.success is True
    assert response.result["message"] == "红旗是什么？"
