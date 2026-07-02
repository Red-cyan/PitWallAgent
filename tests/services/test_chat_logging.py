import json
import logging

from app.schemas.agent import AgentQueryResponse
from app.services.chat_service import ChatService
from app.services.session_service import SessionService


class StubAgentService:
    def handle_query(
        self,
        message: str,
        fallback_intent: str | None = None,
        conversation_context: str | None = None,
    ) -> AgentQueryResponse:
        return AgentQueryResponse(
            intent="race",
            tool_name="race_tool",
            success=True,
            final_answer="下一站比赛是 British Grand Prix。",
            result={},
            error=None,
        )


def test_chat_service_emits_structured_logs(caplog) -> None:
    service = ChatService(
        agent_service=StubAgentService(),
        session_service=SessionService(),
    )

    with caplog.at_level(logging.INFO, logger="pitwall.chat"):
        response = service.handle_chat("下一站比赛是什么？", session_id="session-001")

    assert response.session_id == "session-001"
    events = [json.loads(record.message)["event"] for record in caplog.records if record.name == "pitwall.chat"]
    assert "chat_request_received" in events
    assert "chat_response_generated" in events
