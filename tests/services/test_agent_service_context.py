from app.services.agent_service import AgentService


class StubIntentRouter:
    def route(self, message: str, fallback_intent: str | None = None) -> str:
        if "红旗" in message:
            return "regulation"
        if "车队" in message or "积分榜" in message:
            return "race"
        if fallback_intent and self.looks_like_follow_up(message):
            return fallback_intent
        return "general"

    def looks_like_follow_up(self, message: str) -> bool:
        return message.strip() in {"那呢？", "那呢", "然后呢？"}


class CapturingPlanner:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def plan(self, message: str, fallback_intent: str | None = None) -> dict:
        self.messages.append(message)
        if "车队" in message:
            return {
                "intent": "race",
                "tool_name": "race_tool",
                "action": "get_constructor_standings",
                "params": {},
            }
        return {
            "intent": "race",
            "tool_name": "race_tool",
            "action": "get_driver_standings",
            "params": {},
        }


class StubToolDispatcher:
    def execute_plan(self, plan: dict):
        class Result:
            def __init__(self, tool_name: str, success: bool, payload: dict, error: str | None = None) -> None:
                self.tool_name = tool_name
                self.success = success
                self.payload = payload
                self.error = error

        return Result(
            tool_name=plan["tool_name"],
            success=True,
            payload={"message": plan.get("params", {}).get("question", ""), "action": plan["action"]},
        )


def test_agent_service_does_not_mix_old_context_into_non_follow_up_queries() -> None:
    planner = CapturingPlanner()
    service = AgentService(
        intent_router=StubIntentRouter(),
        planner=planner,
        tool_dispatcher=StubToolDispatcher(),
        runtime=None,
    )
    service.runtime = None

    response = service.handle_query(
        "现在哪只车队是第一名",
        fallback_intent="regulation",
        conversation_context="User: 红旗是什么\nAssistant: 红旗是暂停比赛的信号",
    )

    assert response.intent == "race"
    assert planner.messages[-1] == "现在哪只车队是第一名"


def test_agent_service_keeps_context_for_follow_up_queries() -> None:
    planner = CapturingPlanner()
    service = AgentService(
        intent_router=StubIntentRouter(),
        planner=planner,
        tool_dispatcher=StubToolDispatcher(),
        runtime=None,
    )
    service.runtime = None

    service.handle_query(
        "那呢？",
        fallback_intent="race",
        conversation_context="User: 现在谁是车手积分榜第一名\nAssistant: ...",
    )

    assert "User: 现在谁是车手积分榜第一名" in planner.messages[-1]
