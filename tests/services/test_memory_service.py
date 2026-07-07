from datetime import UTC, datetime

from app.schemas.chat import ConversationTurn
from app.services.memory_service import (
    InMemoryLongTermMemoryStore,
    LongTermMemory,
    MemoryService,
    RedisLongTermMemoryStore,
)
from app.services.session_service import ConversationSession
from tests.services.test_session_service import FakeRedisClient


def test_memory_service_builds_structured_context_with_summary_and_recent_turns() -> None:
    service = MemoryService(store=InMemoryLongTermMemoryStore())
    session = ConversationSession(
        session_id="session-001",
        summary="Earlier the user asked about tyre degradation.",
        compacted_turn_count=6,
        history=[
            ConversationTurn(role="user", message="What is the next race?", created_at=datetime(2026, 7, 1, tzinfo=UTC)),
            ConversationTurn(role="assistant", message="British Grand Prix.", created_at=datetime(2026, 7, 1, tzinfo=UTC)),
        ],
    )

    context = service.build_context(session=session, current_message="What about qualifying?")

    assert context.rendered is not None
    assert "Conversation summary:" in context.rendered
    assert "Recent turns:" in context.rendered
    assert "Current user message:" in context.rendered
    assert context.summary_used is True
    assert context.recent_turn_count == 2
    assert context.compacted_turn_count == 6


def test_memory_service_records_and_retrieves_stable_preferences() -> None:
    store = InMemoryLongTermMemoryStore()
    service = MemoryService(store=store)

    memory = service.record_interaction(
        session_id="session-001",
        user_message="Remember that I prefer technical strategy details.",
        assistant_message="Understood.",
    )

    assert memory is not None
    retrieved = service.retrieve_memories("Can you explain the strategy choice?")
    assert len(retrieved) == 1
    assert "technical strategy details" in retrieved[0].content


def test_memory_service_ignores_one_off_questions() -> None:
    service = MemoryService(store=InMemoryLongTermMemoryStore())

    memory = service.record_interaction(
        session_id="session-001",
        user_message="Who won the last race?",
        assistant_message="The previous race winner was ...",
    )

    assert memory is None
    assert service.retrieve_memories("race winner") == []


def test_redis_long_term_memory_store_round_trip() -> None:
    client = FakeRedisClient()
    store = RedisLongTermMemoryStore(client=client, ttl_seconds=600)
    memory = LongTermMemory(
        memory_id="memory-001",
        content="Remember that I prefer technical strategy details.",
        memory_type="preference",
    )

    store.save(memory)
    loaded = store.list("default")

    assert len(loaded) == 1
    assert loaded[0].memory_id == "memory-001"
    assert loaded[0].content == memory.content
    assert client.ttls["pitwall:memory:memory-001"] == 600
