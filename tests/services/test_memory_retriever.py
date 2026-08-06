import math
from datetime import UTC, datetime

import pytest

from app.services.memory_retriever import SemanticMemoryRetriever
from app.services.memory_service import LongTermMemory, MemoryService, InMemoryLongTermMemoryStore


@pytest.fixture(autouse=True)
def _clear_embedding_cache() -> None:
    SemanticMemoryRetriever._memory_embedding_cache.clear()


def _enable_semantic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.memory_retriever.settings.memory_vector_retrieval_enabled", True)
    monkeypatch.setattr("app.services.memory_service.settings.memory_vector_retrieval_enabled", True)


class StubEmbedder:
    """确定性伪向量：按字符编码生成向量，保证可断言。"""

    def __init__(self) -> None:
        self.embedded_texts: list[list[str]] = []

    def embed_query(self, query: str) -> list[float]:
        return self._vector(query)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.embedded_texts.append(texts)
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        return [float(ord(char)) for char in text]


def _memory(content: str, memory_id: str, confidence: float = 0.7) -> LongTermMemory:
    return LongTermMemory(
        memory_id=memory_id,
        content=content,
        memory_type="preference",
        confidence=confidence,
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
        updated_at=datetime(2026, 7, 1, tzinfo=UTC),
    )


def test_semantic_retriever_ranks_by_cosine_similarity(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_semantic(monkeypatch)
    retriever = SemanticMemoryRetriever(embedder=StubEmbedder())
    memories = [
        _memory("I follow technical strategy details", "m1"),
        _memory("I prefer data about qualifying laps", "m2"),
    ]

    results = retriever.retrieve("strategy analysis please", memories, top_k=2)

    assert results is not None
    assert results[0].memory_id == "m1"


def test_semantic_retriever_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.memory_retriever.settings.memory_vector_retrieval_enabled", False)
    retriever = SemanticMemoryRetriever(embedder=StubEmbedder())

    assert retriever.retrieve("strategy", [_memory("x", "m1")], top_k=1) is None


def test_semantic_retriever_returns_none_on_empty_memories() -> None:
    retriever = SemanticMemoryRetriever(embedder=StubEmbedder())

    assert retriever.retrieve("strategy", [], top_k=1) is None


def test_semantic_retriever_falls_back_on_embedding_failure() -> None:
    class FailingEmbedder(StubEmbedder):
        def embed_query(self, query: str) -> list[float]:
            raise RuntimeError("model down")

    retriever = SemanticMemoryRetriever(embedder=FailingEmbedder())

    assert retriever.retrieve("strategy", [_memory("x", "m1")], top_k=1) is None


def test_semantic_retriever_caches_memory_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_semantic(monkeypatch)
    embedder = StubEmbedder()
    retriever = SemanticMemoryRetriever(embedder=embedder)
    memory = _memory("I prefer technical strategy details", "m1")

    retriever.retrieve("strategy", [memory], top_k=1)
    retriever.retrieve("strategy again", [memory], top_k=1)

    assert len(embedder.embedded_texts) == 1


def test_semantic_retriever_cosine_similarity() -> None:
    retriever = SemanticMemoryRetriever(embedder=StubEmbedder())

    assert math.isclose(retriever._cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
    assert math.isclose(retriever._cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)
    assert retriever._cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_memory_service_uses_semantic_retrieval_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_semantic(monkeypatch)
    monkeypatch.setattr("app.services.memory_service.settings.memory_long_term_enabled", True)
    retriever = SemanticMemoryRetriever(embedder=StubEmbedder())
    store = InMemoryLongTermMemoryStore()
    store.save(_memory("I follow technical strategy details", "m1"))
    store.save(_memory("I prefer data about qualifying laps", "m2"))
    service = MemoryService(store=store, retriever=retriever)

    memories = service.retrieve_memories("strategy analysis please")

    assert len(memories) == 2
    assert memories[0].memory_id == "m1"


def test_memory_service_falls_back_to_lexical_when_retriever_unavailable() -> None:
    store = InMemoryLongTermMemoryStore()
    store.save(_memory("I prefer technical strategy details", "m1"))
    store.save(_memory("I like red bull racing", "m2"))
    service = MemoryService(store=store, retriever=None)

    memories = service.retrieve_memories("strategy choice please")

    assert memories[0].memory_id == "m1"
