from typing import Any, cast

from app.schemas.agent import AgentQueryResponse
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatSessionDeleteResponse,
    ChatSessionListResponse,
    ChatSessionSummary,
)
from app.services.chat_service import ChatService
from app.services.session_service import RedisSessionStore, SessionService
from tests.services.test_session_service import FakeRedisClient


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
    chat_service = ChatService(agent_service=cast(Any, agent_service), session_service=session_service)

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
    chat_service = ChatService(agent_service=cast(Any, agent_service), session_service=session_service)

    response = chat_service.handle_chat("下一站比赛是什么？", session_id="session-001")
    history_response = chat_service.get_history(response.session_id)

    assert isinstance(history_response, ChatHistoryResponse)
    assert history_response.session.session_id == "session-001"
    assert history_response.session.turn_count == 2
    assert history_response.history[0].role == "user"


def test_chat_service_lists_sessions() -> None:
    agent_service = StubAgentService()
    session_service = SessionService()
    chat_service = ChatService(agent_service=cast(Any, agent_service), session_service=session_service)

    chat_service.handle_chat("下一站比赛是什么？", session_id="session-a")
    chat_service.handle_chat("上一站比赛是什么？", session_id="session-b")
    sessions_response = chat_service.list_sessions(limit=10)

    assert isinstance(sessions_response, ChatSessionListResponse)
    assert len(sessions_response.sessions) == 2
    assert sessions_response.sessions[0].session_id == "session-b"


def test_chat_service_returns_single_session_summary() -> None:
    agent_service = StubAgentService()
    session_service = SessionService()
    chat_service = ChatService(agent_service=cast(Any, agent_service), session_service=session_service)

    chat_service.handle_chat("下一站比赛是什么？", session_id="session-a")
    summary = chat_service.get_session("session-a")

    assert isinstance(summary, ChatSessionSummary)
    assert summary.session_id == "session-a"
    assert summary.turn_count == 2


def test_chat_service_deletes_session() -> None:
    agent_service = StubAgentService()
    session_service = SessionService()
    chat_service = ChatService(agent_service=cast(Any, agent_service), session_service=session_service)

    chat_service.handle_chat("下一站比赛是什么？", session_id="session-a")
    result = chat_service.delete_session("session-a")

    assert isinstance(result, ChatSessionDeleteResponse)
    assert result.deleted is True
    assert chat_service.get_session("session-a") is None


def test_chat_service_streams_session_and_status_before_agent_work() -> None:
    agent_service = StubAgentService()
    session_service = SessionService()
    chat_service = ChatService(agent_service=cast(Any, agent_service), session_service=session_service)

    stream = chat_service.stream_chat("下一站比赛是什么？")
    first_event = next(stream)
    second_event = next(stream)

    assert first_event["event"] == "session_started"
    assert second_event["event"] == "status"
    assert second_event["data"]["message"] == "thinking"
    assert agent_service.received_fallback_intent is None

    remaining_events = list(stream)

    remaining_event_names = [event["event"] for event in remaining_events]
    assert remaining_event_names[0] == "message_delta"
    assert remaining_event_names[-1] == "message_completed"
    assert "message_delta" in remaining_event_names
    assert agent_service.received_fallback_intent is None


def test_chat_service_reads_history_after_new_service_instance() -> None:
    redis_client = FakeRedisClient()
    first_session_service = SessionService(store=RedisSessionStore(client=redis_client, ttl_seconds=120))
    first_chat_service = ChatService(
        agent_service=cast(Any, StubAgentService()),
        session_service=first_session_service,
    )

    response = first_chat_service.handle_chat("下一站比赛是什么？", session_id="persistent-session")

    second_session_service = SessionService(store=RedisSessionStore(client=redis_client, ttl_seconds=120))
    second_chat_service = ChatService(
        agent_service=cast(Any, StubAgentService()),
        session_service=second_session_service,
    )
    history_response = second_chat_service.get_history(response.session_id)

    assert history_response.session.session_id == "persistent-session"
    assert history_response.session.turn_count == 2
    assert history_response.history[0].message == "下一站比赛是什么？"
    assert history_response.history[1].message == "下一站比赛是 British Grand Prix。"
