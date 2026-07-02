from app.schemas.agent import AgentQueryResponse
from app.services.chat_service import ChatService
from app.services.session_service import SessionService


class StubAgentService:
    def __init__(self) -> None:
        self.received_fallback_intent: str | None = None

    def handle_query(self, message: str, fallback_intent: str | None = None) -> AgentQueryResponse:
        self.received_fallback_intent = fallback_intent
        if "那呢" in message:
            return AgentQueryResponse(
                intent=fallback_intent or "news",
                tool_name="race_tool" if fallback_intent == "race" else "news_tool",
                success=True,
                final_answer="上一站比赛是 Austrian Grand Prix。",
                result={},
                error=None,
            )

        return AgentQueryResponse(
            intent="race",
            tool_name="race_tool",
            success=True,
            final_answer="下一站比赛是 British Grand Prix。",
            result={},
            error=None,
        )


def test_chat_service_reuses_session_and_passes_last_intent() -> None:
    agent_service = StubAgentService()
    session_service = SessionService()
    chat_service = ChatService(agent_service=agent_service, session_service=session_service)

    first_response = chat_service.handle_chat("下一站比赛是什么？")
    second_response = chat_service.handle_chat("那呢？", session_id=first_response.session_id)

    assert second_response.session_id == first_response.session_id
    assert agent_service.received_fallback_intent == "race"
    assert second_response.response.intent == "race"
    assert len(second_response.history) == 4
