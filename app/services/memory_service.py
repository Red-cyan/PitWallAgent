from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from typing import Protocol
from uuid import uuid4

from app.config.settings import settings
from app.schemas.chat import ConversationTurn
from app.services.session_service import ConversationSession, RedisClientProtocol, SessionStoreFactory


@dataclass
class LongTermMemory:
    memory_id: str
    content: str
    memory_type: str
    owner_id: str = "default"
    confidence: float = 0.7
    source_session_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MemoryContext:
    rendered: str | None
    recent_turn_count: int = 0
    long_term_memory_count: int = 0
    estimated_context_tokens: int = 0
    summary_used: bool = False
    compacted_turn_count: int = 0
    compression_mode: str | None = None
    compression_fallback: bool = False
    compression_input_tokens: int = 0
    compression_output_tokens: int = 0

    def trace(self) -> dict[str, object]:
        return {
            "memory_summary_used": self.summary_used,
            "memory_recent_turn_count": self.recent_turn_count,
            "memory_long_term_count": self.long_term_memory_count,
            "memory_estimated_context_tokens": self.estimated_context_tokens,
            "memory_compacted_turn_count": self.compacted_turn_count,
            "memory_compression_mode": self.compression_mode,
            "memory_compression_fallback": self.compression_fallback,
            "memory_compression_input_tokens": self.compression_input_tokens,
            "memory_compression_output_tokens": self.compression_output_tokens,
        }


class LongTermMemoryStore(Protocol):
    def save(self, memory: LongTermMemory) -> None:
        ...

    def list(self, owner_id: str = "default") -> list[LongTermMemory]:
        ...


class InMemoryLongTermMemoryStore:
    def __init__(self) -> None:
        self._memories: dict[str, LongTermMemory] = {}

    def save(self, memory: LongTermMemory) -> None:
        self._memories[memory.memory_id] = memory

    def list(self, owner_id: str = "default") -> list[LongTermMemory]:
        return [
            memory
            for memory in self._memories.values()
            if memory.owner_id == owner_id
        ]


class RedisLongTermMemoryStore:
    KEY_PREFIX = "pitwall:memory:"
    INDEX_PREFIX = "pitwall:memories:index:"

    def __init__(
        self,
        client: RedisClientProtocol,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds or settings.memory_long_term_ttl_seconds

    def save(self, memory: LongTermMemory) -> None:
        self.client.set(
            self._memory_key(memory.memory_id),
            self._serialize(memory),
            ex=self.ttl_seconds,
        )
        self.client.zadd(
            self._index_key(memory.owner_id),
            {memory.memory_id: memory.updated_at.timestamp()},
        )

    def list(self, owner_id: str = "default") -> list[LongTermMemory]:
        memory_ids = self.client.zrevrange(
            self._index_key(owner_id),
            0,
            max(settings.memory_long_term_top_k * 5, 20),
        )
        memories: list[LongTermMemory] = []
        for memory_id in memory_ids:
            if isinstance(memory_id, bytes):
                memory_id = memory_id.decode("utf-8")
            payload = self.client.get(self._memory_key(memory_id))
            if payload is None:
                continue
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            memories.append(self._deserialize(payload))
        return memories

    def _memory_key(self, memory_id: str) -> str:
        return f"{self.KEY_PREFIX}{memory_id}"

    def _index_key(self, owner_id: str) -> str:
        return f"{self.INDEX_PREFIX}{owner_id}"

    def _serialize(self, memory: LongTermMemory) -> str:
        payload = {
            "memory_id": memory.memory_id,
            "content": memory.content,
            "memory_type": memory.memory_type,
            "owner_id": memory.owner_id,
            "confidence": memory.confidence,
            "source_session_id": memory.source_session_id,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat(),
        }
        return json.dumps(payload, ensure_ascii=False)

    def _deserialize(self, payload: str) -> LongTermMemory:
        data = json.loads(payload)
        return LongTermMemory(
            memory_id=data["memory_id"],
            content=data["content"],
            memory_type=data["memory_type"],
            owner_id=data.get("owner_id", "default"),
            confidence=float(data.get("confidence", 0.7)),
            source_session_id=data.get("source_session_id"),
            created_at=datetime.fromisoformat(data["created_at"]).astimezone(UTC),
            updated_at=datetime.fromisoformat(data["updated_at"]).astimezone(UTC),
        )


class LongTermMemoryStoreFactory:
    @staticmethod
    def create() -> LongTermMemoryStore:
        backend = settings.memory_long_term_backend.lower()
        if backend == "memory":
            return InMemoryLongTermMemoryStore()
        if backend == "redis":
            return RedisLongTermMemoryStore(
                client=SessionStoreFactory._build_redis_client(),
                ttl_seconds=settings.memory_long_term_ttl_seconds,
            )
        raise ValueError(f"Unsupported memory_long_term_backend: {settings.memory_long_term_backend}")


class MemoryService:
    def __init__(
        self,
        store: LongTermMemoryStore | None = None,
        *,
        owner_id: str = "default",
    ) -> None:
        self.store = store or LongTermMemoryStoreFactory.create()
        self.owner_id = owner_id

    def build_context(
        self,
        *,
        session: ConversationSession,
        current_message: str,
    ) -> MemoryContext:
        recent_turns = session.history[-max(1, settings.memory_recent_turns) :]
        long_term_memories = self.retrieve_memories(current_message)

        sections: list[str] = []
        if session.summary:
            sections.append(f"Conversation summary:\n{session.summary.strip()}")

        if long_term_memories:
            memory_lines = [f"- {memory.content}" for memory in long_term_memories]
            sections.append("Long-term memory:\n" + "\n".join(memory_lines))

        if recent_turns:
            sections.append("Recent turns:\n" + self._format_turns(recent_turns))

        if not sections:
            return MemoryContext(rendered=None)

        sections.append(f"Current user message:\nUser: {current_message}")
        rendered = "\n\n".join(sections)
        rendered = self._fit_context_budget(rendered, current_message, recent_turns, session.summary)
        return MemoryContext(
            rendered=rendered,
            recent_turn_count=len(recent_turns),
            long_term_memory_count=len(long_term_memories),
            estimated_context_tokens=self.estimate_tokens(rendered),
            summary_used=bool(session.summary),
            compacted_turn_count=session.compacted_turn_count,
            compression_mode=session.compression_mode,
            compression_fallback=session.compression_fallback,
            compression_input_tokens=session.compression_input_tokens,
            compression_output_tokens=session.compression_output_tokens,
        )

    def record_interaction(
        self,
        *,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> LongTermMemory | None:
        if not settings.memory_long_term_enabled:
            return None

        memory = self._extract_memory(
            session_id=session_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )
        if memory is None:
            return None

        self.store.save(memory)
        return memory

    def retrieve_memories(self, query: str) -> list[LongTermMemory]:
        if not settings.memory_long_term_enabled:
            return []

        memories = self.store.list(self.owner_id)
        if not memories:
            return []

        query_terms = self._terms(query)
        scored: list[tuple[float, LongTermMemory]] = []
        for memory in memories:
            memory_terms = self._terms(memory.content)
            overlap = len(query_terms & memory_terms)
            score = overlap + memory.confidence
            scored.append((score, memory))

        scored.sort(
            key=lambda item: (item[0], item[1].updated_at),
            reverse=True,
        )
        return [memory for _, memory in scored[: max(0, settings.memory_long_term_top_k)]]

    def estimate_tokens(self, text: str | None) -> int:
        if not text:
            return 0
        ascii_chars = sum(1 for char in text if ord(char) < 128)
        non_ascii_chars = len(text) - ascii_chars
        return max(1, (ascii_chars // 4) + non_ascii_chars)

    def _format_turns(self, turns: list[ConversationTurn]) -> str:
        lines: list[str] = []
        for turn in turns:
            role = "User" if turn.role == "user" else "Assistant"
            lines.append(f"{role}: {turn.message}")
        return "\n".join(lines)

    def _fit_context_budget(
        self,
        rendered: str,
        current_message: str,
        recent_turns: list[ConversationTurn],
        summary: str | None,
    ) -> str:
        budget = settings.memory_context_token_budget
        if budget <= 0 or self.estimate_tokens(rendered) <= budget:
            return rendered

        # Keep the active question and recent turns intact before trimming memory.
        required = f"Recent turns:\n{self._format_turns(recent_turns)}\n\nCurrent user message:\nUser: {current_message}"
        if self.estimate_tokens(required) > budget:
            return self._truncate_to_budget(required, budget)
        remaining = budget - self.estimate_tokens(required)
        if summary and remaining > 0:
            summary_section = f"Conversation summary:\n{summary.strip()}"
            max_chars = max(remaining * 3, 40)
            summary_section = summary_section[:max_chars]
            return f"{summary_section}\n\n{required}" if self.estimate_tokens(summary_section) <= remaining else required
        return required

    def _truncate_to_budget(self, text: str, budget: int) -> str:
        low, high = 0, len(text)
        while low < high:
            midpoint = (low + high + 1) // 2
            candidate = text[-midpoint:].lstrip()
            if self.estimate_tokens(candidate) <= budget:
                low = midpoint
            else:
                high = midpoint - 1
        return text[-low:].lstrip() if low else ""

    def _extract_memory(
        self,
        *,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> LongTermMemory | None:
        normalized = user_message.strip()
        lowered = normalized.lower()
        preference_markers = (
            "remember",
            "from now on",
            "default",
            "prefer",
            "use chinese",
            "use english",
            "记住",
            "以后",
            "默认",
            "偏好",
            "喜欢",
            "关注",
            "用中文",
            "用英文",
        )
        if not any(marker in lowered or marker in normalized for marker in preference_markers):
            return None

        content = " ".join(normalized.split())
        if len(content) > 240:
            content = content[:237].rstrip() + "..."

        memory_type = "preference"
        if any(marker in lowered or marker in normalized for marker in ("关注", "follow", "interested")):
            memory_type = "topic_interest"

        if assistant_message:
            confidence = 0.8
        else:
            confidence = 0.6

        return LongTermMemory(
            memory_id=uuid4().hex,
            content=content,
            memory_type=memory_type,
            owner_id=self.owner_id,
            confidence=confidence,
            source_session_id=session_id,
        )

    def _terms(self, text: str) -> set[str]:
        normalized = text.lower()
        ascii_terms = {
            token.strip(".,?!:;()[]")
            for token in normalized.split()
            if len(token.strip(".,?!:;()[]")) >= 3
        }
        cjk_terms = {char for char in text if "\u4e00" <= char <= "\u9fff"}
        return ascii_terms | cjk_terms
