from app.schemas.agent import AgentQueryResponse
from app.services import session_service
from app.services.session_service import (
    InMemorySessionStore,
    RedisSessionStore,
    SessionService,
    SessionStoreFactory,
)


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def setex(self, key: str, time: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = time


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


def test_redis_session_store_round_trip() -> None:
    client = FakeRedisClient()
    store = RedisSessionStore(client=client, ttl_seconds=120)

    service = SessionService(store=store)
    session = service.get_or_create_session("session-redis")
    service.append_user_message(session.session_id, "下一站比赛是什么？")

    loaded_session = store.get("session-redis")

    assert loaded_session is not None
    assert loaded_session.session_id == "session-redis"
    assert loaded_session.history[0].message == "下一站比赛是什么？"
    assert client.ttls["pitwall:session:session-redis"] == 120


def test_session_store_factory_returns_redis_store(monkeypatch) -> None:
    monkeypatch.setattr(session_service.settings, "session_backend", "redis")
    monkeypatch.setattr(session_service.settings, "session_ttl_seconds", 300)
    monkeypatch.setattr(
        SessionStoreFactory,
        "_build_redis_client",
        staticmethod(lambda: FakeRedisClient()),
    )

    store = SessionStoreFactory.create()

    assert isinstance(store, RedisSessionStore)
    assert store.ttl_seconds == 300
