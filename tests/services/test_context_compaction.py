import json
from typing import Any, cast

import pytest

from app.schemas.agent import AgentQueryResponse
from app.schemas.chat import ConversationTurn
from app.services.chat_service import ChatService
from app.services.context_compaction import ContextCompactionService
from app.services.session_service import (
    ConversationSession,
    InMemorySessionStore,
    RedisSessionStore,
    SessionService,
)
from tests.services.test_session_service import FakeRedisClient


class StubSummaryLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[list[dict[str, Any]]] = []

    def chat(self, messages, **kwargs) -> str:
        self.calls.append(messages)
        return self.response


def turn(role: str, message: str) -> ConversationTurn:
    from datetime import UTC, datetime

    return ConversationTurn(role=role, message=message, created_at=datetime.now(UTC))


def test_incremental_compaction_sends_existing_summary_and_evicted_turns(monkeypatch) -> None:
    monkeypatch.setattr("app.services.context_compaction.settings.memory_compression_enabled", True)
    llm = StubSummaryLLM('{"topic":"race","facts":["new fact"],"preferences":[],"open_loops":[],"entities":[]}')
    service = ContextCompactionService(llm_client=cast(Any, llm))

    result = service.compact(
        '{"topic":"race","facts":["old fact"],"preferences":[],"open_loops":[],"entities":[]}',
        [turn("user", "Ask about tyre wear")],
    )

    assert "Existing memory" in llm.calls[0][1]["content"]
    assert "Ask about tyre wear" in llm.calls[0][1]["content"]
    payload = json.loads(result.summary)
    assert payload["facts"] == ["old fact", "new fact"]
    assert result.fallback is False


@pytest.mark.parametrize("response", ["not json", "```json\nnot json\n```"])
def test_invalid_summary_response_uses_deterministic_fallback(response, monkeypatch) -> None:
    monkeypatch.setattr("app.services.context_compaction.settings.memory_compression_enabled", True)
    service = ContextCompactionService(llm_client=cast(Any, StubSummaryLLM(response)))

    result = service.compact("User prefers concise answers.", [turn("user", "Follow up on tyres")])

    payload = json.loads(result.summary)
    assert result.fallback is True
    assert any("Legacy summary" in fact for fact in payload["facts"])
    assert any("Follow up on tyres" in fact for fact in payload["facts"])


def test_llm_exception_does_not_fail_compaction(monkeypatch) -> None:
    class FailingLLM(StubSummaryLLM):
        def chat(self, messages, **kwargs) -> str:
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.services.context_compaction.settings.memory_compression_enabled", True)
    result = ContextCompactionService(llm_client=cast(Any, FailingLLM(""))).compact(
        None, [turn("user", "Remember this")]
    )

    assert result.fallback is True
    assert "Remember this" in result.summary


def test_redis_round_trip_preserves_structured_summary() -> None:
    client = FakeRedisClient()
    store = RedisSessionStore(client=client, ttl_seconds=120)
    summary = json.dumps({"topic": "race", "facts": ["fact"], "preferences": [], "open_loops": [], "entities": []})
    store.save(ConversationSession(session_id="structured", summary=summary))

    loaded = store.get("structured")

    assert loaded is not None
    assert loaded.summary == summary


def test_chat_request_compacts_once_after_assistant_message(monkeypatch) -> None:
    monkeypatch.setattr("app.services.session_service.settings.memory_compaction_token_threshold", 1)
    monkeypatch.setattr("app.services.session_service.settings.memory_recent_turns", 1)

    class CountingCompactor:
        def __init__(self) -> None:
            self.calls = 0

        def compact(self, existing_summary, turns):
            from app.services.context_compaction import CompactionResult

            self.calls += 1
            return CompactionResult("{}", "deterministic", True, 1, 1)

    class Agent:
        def handle_query(self, message, **kwargs):
            return AgentQueryResponse(intent="general", tool_name="general_tool", success=True, final_answer="answer", result={})

    compactor = CountingCompactor()
    sessions = SessionService(store=InMemorySessionStore(), compaction_service=cast(Any, compactor))
    response = ChatService(agent_service=cast(Any, Agent()), session_service=sessions).handle_chat("question")

    assert response.session_id
    assert compactor.calls == 1
