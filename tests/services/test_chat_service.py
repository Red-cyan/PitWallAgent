from datetime import UTC, datetime

from app.schemas.agent import AgentQueryResponse
from app.schemas.chat import ChatHistoryResponse, ChatSessionListResponse, ChatSessionSummary, ConversationTurn
from app.services.chat_service import ChatService
from app.services.session_service import SessionService


class StubAgentService:
    def __init__(self) -> None:
        self.received_fallback_intent: str | None = None
        self.received_conversation_context: str | None = None

    def handle_query(
        self,
        message: str,
        fallback_intent: str | None = None,
        conversation_context: str | None = None,
    ) -> AgentQueryResponse:
        self.received_fallback_intent = fallback_intent
        self.received_conversation_context = conversation_context
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
    assert agent_service.received_conversation_context is not None
    assert "下一站比赛是 British Grand Prix。" in agent_service.received_conversation_context
    assert second_response.response.intent == "race"
    assert len(second_response.history) == 4
    assert second_response.session.turn_count == 4
    assert second_response.session.last_intent == "race"


def test_chat_service_returns_history() -> None:
    agent_service = StubAgentService()
    session_service = SessionService()
    chat_service = ChatService(agent_service=agent_service, session_service=session_service)

    response = chat_service.handle_chat("下一站比赛是什么？", session_id="session-001")
    history_response = chat_service.get_history(response.session_id)

    assert isinstance(history_response, ChatHistoryResponse)
    assert history_response.session.session_id == "session-001"
    assert history_response.session.turn_count == 2
    assert history_response.history[0].role == "user"


def test_chat_service_lists_sessions() -> None:
    agent_service = StubAgentService()
    session_service = SessionService()
    chat_service = ChatService(agent_service=agent_service, session_service=session_service)

    chat_service.handle_chat("下一站比赛是什么？", session_id="session-a")
    chat_service.handle_chat("上一站比赛是什么？", session_id="session-b")
    sessions_response = chat_service.list_sessions(limit=10)

    assert isinstance(sessions_response, ChatSessionListResponse)
    assert len(sessions_response.sessions) == 2
    assert sessions_response.sessions[0].session_id == "session-b"
