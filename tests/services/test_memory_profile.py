from dataclasses import replace
from typing import cast

from sqlalchemy import Table, create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import UserMemoryRecord
from app.services.memory_service import (
    InMemoryLongTermMemoryStore,
    LongTermMemory,
    MemoryExtractor,
    MemoryService,
    PostgresLongTermMemoryStore,
)


def _new_service() -> MemoryService:
    return MemoryService(store=InMemoryLongTermMemoryStore())


def test_constraint_memories_overwrite_previous_value(monkeypatch) -> None:
    """LLM 路径下，同一 key 的约束更新时覆盖旧值。"""

    class StubLLM:
        def __init__(self) -> None:
            self.calls = 0

        def chat(self, messages, **kwargs):  # noqa: ANN001
            self.calls += 1
            value = "use Chinese" if self.calls == 2 else "use English"
            return (
                '{"memories":[{"category":"constraint","key":"language",'
                '"value":"' + value + '"}]}'
            )

    monkeypatch.setattr("app.services.memory_service.settings.llm_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.memory_service.settings.memory_extraction_enabled", True
    )
    service = MemoryService(
        store=InMemoryLongTermMemoryStore(),
        extractor=MemoryExtractor(llm_client=StubLLM()),
    )

    service.record_interaction(
        session_id="session-1",
        user_message="必须用英文回复",
        assistant_message="好的",
    )
    service.record_interaction(
        session_id="session-1",
        user_message="必须用中文回复",
        assistant_message="好的",
    )

    memories = service.retrieve_memories("回复语言")

    assert len(memories) == 1
    assert "Chinese" in memories[0].content


def test_preference_memories_are_appended_incrementally() -> None:
    service = _new_service()

    service.record_interaction(
        session_id="session-1",
        user_message="我喜欢研究进站策略",
        assistant_message="好的",
    )
    service.record_interaction(
        session_id="session-1",
        user_message="我还喜欢研究轮胎管理",
        assistant_message="好的",
    )

    memories = service.retrieve_memories("策略 轮胎")

    assert len(memories) == 2
    contents = " ".join(memory.content for memory in memories)
    assert "进站策略" in contents
    assert "轮胎管理" in contents


def test_memories_are_scoped_per_user() -> None:
    store = InMemoryLongTermMemoryStore()
    service = MemoryService(store=store)

    service.record_interaction(
        session_id="s1",
        user_message="我喜欢数据解说",
        assistant_message="好的",
        owner_id="user-a",
    )
    service.record_interaction(
        session_id="s2",
        user_message="我不喜欢数据解说",
        assistant_message="好的",
        owner_id="user-b",
    )

    assert len(service.retrieve_memories("数据", owner_id="user-a")) == 1
    assert len(service.retrieve_memories("数据", owner_id="user-b")) == 1
    content_a = service.retrieve_memories("数据", owner_id="user-a")[0].content
    content_b = service.retrieve_memories("数据", owner_id="user-b")[0].content
    assert content_a != content_b


def test_llm_extraction_parses_structured_memory(monkeypatch) -> None:
    class StubLLM:
        def chat(self, messages, **kwargs):  # noqa: ANN001
            return '{"memories":[{"category":"constraint","key":"language","value":"always use English"}]}'

    monkeypatch.setattr("app.services.memory_service.settings.llm_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.memory_service.settings.memory_extraction_enabled", True
    )
    extractor = MemoryExtractor(llm_client=StubLLM())

    extracted = extractor.extract(
        user_message="Please always use English in replies.",
        assistant_message="Sure.",
    )

    assert len(extracted) == 1
    assert extracted[0].category == "constraint"
    assert extracted[0].key == "language"
    assert extracted[0].value == "always use English"


def test_llm_empty_result_does_not_fall_back_to_keyword(monkeypatch) -> None:
    """LLM 明确表示无持久信息时，不得再用关键词降级误存画像。"""

    class StubEmptyLLM:
        def chat(self, messages, **kwargs):  # noqa: ANN001
            return '{"memories": []}'

    monkeypatch.setattr("app.services.memory_service.settings.llm_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.memory_service.settings.memory_extraction_enabled", True
    )
    extractor = MemoryExtractor(llm_client=StubEmptyLLM())

    extracted = extractor.extract(
        user_message="必须用中文回复",
        assistant_message="好的",
    )

    assert extracted == []


def test_keyword_constraints_do_not_overwrite_each_other() -> None:
    """关键词降级下不同约束使用内容作 key，各自独立存在。"""
    service = _new_service()

    service.record_interaction(
        session_id="session-1",
        user_message="必须用中文回复",
        assistant_message="好的",
    )
    service.record_interaction(
        session_id="session-1",
        user_message="不要提2026赛季",
        assistant_message="好的",
    )

    memories = service.retrieve_memories("约束")

    assert len(memories) == 2
    contents = " ".join(memory.content for memory in memories)
    assert "中文" in contents
    assert "2026" in contents


def test_same_keyword_constraint_replaces_previous_value() -> None:
    """同一约束重复声明时按 key 覆盖旧值，不重复追加。"""
    service = _new_service()

    service.record_interaction(
        session_id="session-1",
        user_message="必须用中文回复",
        assistant_message="好的",
    )
    service.record_interaction(
        session_id="session-1",
        user_message="必须用中文回复",
        assistant_message="好的",
    )

    memories = service.retrieve_memories("约束")

    assert len(memories) == 1
    assert "中文" in memories[0].content


def test_postgres_store_round_trip_and_overwrite() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    cast(Table, UserMemoryRecord.__table__).create(bind=engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )
    store = PostgresLongTermMemoryStore(session_factory=session_factory)

    memory = LongTermMemory(
        memory_id="memory-001",
        content="prefer English",
        memory_type="preference",
        owner_id="user-1",
        memory_key="preference:language",
    )
    store.save(memory)

    loaded = store.list("user-1")
    assert len(loaded) == 1
    assert loaded[0].content == "prefer English"
    assert store.find_by_key("user-1", "preference:language") is not None

    updated = replace(
        loaded[0], content="prefer Chinese", updated_at=loaded[0].updated_at
    )
    store.save(updated)

    after = store.list("user-1")
    assert len(after) == 1
    assert after[0].content == "prefer Chinese"
