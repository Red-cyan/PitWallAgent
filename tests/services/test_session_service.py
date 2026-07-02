from app.schemas.agent import AgentQueryResponse
from app.services import session_service
from app.services.session_service import InMemorySessionStore, SessionService, SessionStoreFactory


def test_session_service_creates_session_and_tracks_history() -> None:
    service = SessionService()

    session = service.get_or_create_session()
    service.append_user_message(session.session_id, "下一站比赛是什么？")
    service.append_agent_response(
        session.session_id,
        AgentQueryResponse(
            intent="race",
            tool_name="race_tool",
            success=True,
            final_answer="下一站比赛是 British Grand Prix。",
            result={},
            error=None,
        ),
    )

    history = service.get_history(session.session_id)

    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].role == "assistant"
    assert service.get_last_intent(session.session_id) == "race"


def test_session_store_factory_returns_memory_store(monkeypatch) -> None:
    monkeypatch.setattr(session_service.settings, "session_backend", "memory")

    store = SessionStoreFactory.create()

    assert isinstance(store, InMemorySessionStore)


def test_session_service_trims_history_to_configured_limit(monkeypatch) -> None:
    monkeypatch.setattr(session_service.settings, "session_history_max_turns", 2)
    service = SessionService(store=InMemorySessionStore())

    session = service.get_or_create_session("session-001")
    service.append_user_message(session.session_id, "第一句")
    service.append_user_message(session.session_id, "第二句")
    service.append_user_message(session.session_id, "第三句")

    history = service.get_history(session.session_id)

    assert len(history) == 2
    assert history[0].message == "第二句"
    assert history[1].message == "第三句"
