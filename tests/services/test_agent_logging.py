import json
import logging

from app.schemas.agent import AgentQueryResponse
from app.services.agent_service import AgentService


class StubIntentRouter:
    def route(self, message: str, fallback_intent: str | None = None) -> str:
        return "race"


class StubToolDispatcher:
    def dispatch(self, intent: str, message: str):
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


class StubRuntime:
    def run(
        self,
        message: str,
        fallback_intent: str | None = None,
    ) -> AgentQueryResponse:
        return AgentQueryResponse(
            intent="race",
            tool_name="race_tool",
            success=True,
            final_answer="graph answer",
            result={"mode": "graph"},
            error=None,
        )


def test_agent_service_emits_structured_logs_for_fallback_path(caplog) -> None:
    service = AgentService(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        runtime=None,
    )
    service.runtime = None

    with caplog.at_level(logging.INFO, logger="pitwall.agent"):
        response = service.handle_query("车手积分榜第一是谁？")

    assert response.intent == "race"
    payloads = [json.loads(record.message) for record in caplog.records if record.name == "pitwall.agent"]
    assert payloads[0]["event"] == "agent_query_received"
    assert payloads[-1]["event"] == "agent_query_completed"
    assert payloads[-1]["runtime_mode"] == "fallback"


def test_agent_service_emits_structured_logs_for_runtime_path(caplog) -> None:
    service = AgentService(
        intent_router=StubIntentRouter(),
        tool_dispatcher=StubToolDispatcher(),
        runtime=StubRuntime(),
    )

    with caplog.at_level(logging.INFO, logger="pitwall.agent"):
        response = service.handle_query("车手积分榜第一是谁？")

    assert response.result["mode"] == "graph"
    payloads = [json.loads(record.message) for record in caplog.records if record.name == "pitwall.agent"]
    assert payloads[-1]["runtime_mode"] == "langgraph"
