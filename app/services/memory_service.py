from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select

from app.config.settings import settings
from app.db.engine import SessionLocal
from app.db.models import UserMemoryRecord
from app.schemas.chat import ConversationTurn
from app.services.session_service import (
    ConversationSession,
    RedisClientProtocol,
    SessionStoreFactory,
)

OVERWRITE_CATEGORIES = frozenset({"constraint", "fact", "identity", "contact"})
ACCUMULATE_CATEGORIES = frozenset(
    {"preference", "history", "interest", "topic_interest"}
)

MEMORY_EXTRACTION_SYSTEM_PROMPT = (
    "You are a lightweight long-term memory extraction component for an AI assistant.\n"
    "From the latest user turn, extract only durable, long-lived information about the user "
    "(preferences, constraints, stable facts, significant past behavior).\n"
    "Return JSON only with exactly this shape:\n"
    '{"memories":[{"category":"preference|constraint|fact|history","key":"stable identifier","value":"concise stored text"}]}\n'
    "Rules:\n"
    "- preference: likes, dislikes, interests, language, style (accumulate over time)\n"
    "- constraint: must/never/cannot, address, contact, limits (overwrite when changed)\n"
    "- fact: stable attributes about the user (overwrite when changed)\n"
    "- history: significant past behavior or events (accumulate over time)\n"
    "- Do NOT extract transient questions, greetings, or one-off requests.\n"
    '- Keep values concise (under 200 chars). If nothing durable, return {"memories": []}.'
)

PREFERENCE_MARKERS = (
    "remember",
    "from now on",
    "prefer",
    "like",
    "use chinese",
    "use english",
    "记住",
    "以后",
    "默认",
    "偏好",
    "喜欢",
    "习惯",
    "用中文",
    "用英文",
)
INTEREST_MARKERS = (
    "关注",
    "follow",
    "interested",
    "兴趣",
)
CONSTRAINT_MARKERS = (
    "never",
    "always",
    "must",
    "cannot",
    "don't",
    "不要",
    "禁止",
    "不能",
    "必须",
    "别",
)


@dataclass
class LongTermMemory:
    memory_id: str
    content: str
    memory_type: str
    owner_id: str = "default"
    confidence: float = 0.7
    source_session_id: str | None = None
    memory_key: str | None = None
    metadata: dict | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ExtractedMemory:
    category: str
    key: str
    value: str
    confidence: float = 0.7


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
    memory_retrieval_mode: str = "disabled"

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
            "memory_retrieval_mode": self.memory_retrieval_mode,
        }


class LongTermMemoryStore(Protocol):
    def save(self, memory: LongTermMemory) -> None: ...

    def list(self, owner_id: str = "default") -> list[LongTermMemory]: ...

    def find_by_key(self, owner_id: str, memory_key: str) -> LongTermMemory | None: ...


class MemoryRetriever(Protocol):
    """语义记忆召回接口；不可用时返回 None 以触发词法回退。"""

    def retrieve(
        self,
        query: str,
        memories: list[LongTermMemory],
        top_k: int,
    ) -> list[LongTermMemory] | None: ...


class InMemoryLongTermMemoryStore:
    def __init__(self) -> None:
        self._memories: dict[str, LongTermMemory] = {}

    def save(self, memory: LongTermMemory) -> None:
        self._memories[memory.memory_id] = memory

    def list(self, owner_id: str = "default") -> list[LongTermMemory]:
        return [
            memory for memory in self._memories.values() if memory.owner_id == owner_id
        ]

    def find_by_key(self, owner_id: str, memory_key: str) -> LongTermMemory | None:
        for memory in self._memories.values():
            if memory.owner_id == owner_id and memory.memory_key == memory_key:
                return memory
        return None


class RedisLongTermMemoryStore:
    KEY_PREFIX = "pitwall:memory:"
    INDEX_PREFIX = "pitwall:memories:index:"
    KEY_INDEX_PREFIX = "pitwall:memories:key:"

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
        if memory.memory_key:
            self.client.set(
                self._key_index_key(memory.owner_id, memory.memory_key),
                memory.memory_id,
                ex=self.ttl_seconds,
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
            memory = self._load(memory_id)
            if memory is not None:
                memories.append(memory)
        return memories

    def find_by_key(self, owner_id: str, memory_key: str) -> LongTermMemory | None:
        payload = self.client.get(self._key_index_key(owner_id, memory_key))
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return self._load(payload)

    def _load(self, memory_id: str) -> LongTermMemory | None:
        payload = self.client.get(self._memory_key(memory_id))
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return self._deserialize(payload)

    def _memory_key(self, memory_id: str) -> str:
        return f"{self.KEY_PREFIX}{memory_id}"

    def _index_key(self, owner_id: str) -> str:
        return f"{self.INDEX_PREFIX}{owner_id}"

    def _key_index_key(self, owner_id: str, memory_key: str) -> str:
        return f"{self.KEY_INDEX_PREFIX}{owner_id}:{memory_key}"

    def _serialize(self, memory: LongTermMemory) -> str:
        payload = {
            "memory_id": memory.memory_id,
            "content": memory.content,
            "memory_type": memory.memory_type,
            "owner_id": memory.owner_id,
            "confidence": memory.confidence,
            "source_session_id": memory.source_session_id,
            "memory_key": memory.memory_key,
            "metadata": memory.metadata,
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
            memory_key=data.get("memory_key"),
            metadata=data.get("metadata"),
            created_at=datetime.fromisoformat(data["created_at"]).astimezone(UTC),
            updated_at=datetime.fromisoformat(data["updated_at"]).astimezone(UTC),
        )


class PostgresLongTermMemoryStore:
    """PostgreSQL user profile store.

    Memories are scoped by user_id. Overwrite-style categories
    (constraint/fact) are upserted on (user_id, memory_key), while
    preference-style categories are appended with distinct keys.
    """

    def __init__(self, session_factory: Any | None = None) -> None:
        self._session_factory = session_factory or SessionLocal

    def save(self, memory: LongTermMemory) -> None:
        with self._session() as session:
            record = session.execute(
                select(UserMemoryRecord).where(
                    UserMemoryRecord.memory_id == memory.memory_id
                )
            ).scalar_one_or_none()
            now = memory.updated_at or datetime.now(UTC)
            if record is None:
                record = UserMemoryRecord(
                    memory_id=memory.memory_id,
                    user_id=memory.owner_id,
                    memory_key=memory.memory_key
                    or f"{memory.memory_type}:{uuid4().hex[:12]}",
                    category=memory.memory_type,
                    content=memory.content,
                    confidence=memory.confidence,
                    source_session_id=memory.source_session_id,
                    memory_metadata=memory.metadata,
                    created_at=memory.created_at or datetime.now(UTC),
                    updated_at=now,
                )
                session.add(record)
            else:
                if memory.memory_key:
                    record.memory_key = memory.memory_key
                record.category = memory.memory_type
                record.content = memory.content
                record.confidence = memory.confidence
                record.source_session_id = memory.source_session_id
                record.memory_metadata = memory.metadata
                record.updated_at = now
            session.commit()

    def list(self, owner_id: str = "default") -> list[LongTermMemory]:
        with self._session() as session:
            records = (
                session.execute(
                    select(UserMemoryRecord)
                    .where(UserMemoryRecord.user_id == owner_id)
                    .order_by(UserMemoryRecord.updated_at.desc())
                )
                .scalars()
                .all()
            )
            return [self._to_memory(record) for record in records]

    def find_by_key(self, owner_id: str, memory_key: str) -> LongTermMemory | None:
        with self._session() as session:
            record = session.execute(
                select(UserMemoryRecord).where(
                    UserMemoryRecord.user_id == owner_id,
                    UserMemoryRecord.memory_key == memory_key,
                )
            ).scalar_one_or_none()
            return self._to_memory(record) if record is not None else None

    @staticmethod
    def _to_memory(record: UserMemoryRecord) -> LongTermMemory:
        return LongTermMemory(
            memory_id=record.memory_id,
            content=record.content,
            memory_type=record.category,
            owner_id=record.user_id,
            confidence=record.confidence,
            source_session_id=record.source_session_id,
            memory_key=record.memory_key,
            metadata=record.memory_metadata,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @contextmanager
    def _session(self) -> Any:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class LongTermMemoryStoreFactory:
    @staticmethod
    def create() -> LongTermMemoryStore:
        backend = settings.memory_long_term_backend.lower()
        if backend == "memory":
            return InMemoryLongTermMemoryStore()
        if backend == "postgres":
            return PostgresLongTermMemoryStore()
        if backend == "redis":
            return RedisLongTermMemoryStore(
                client=SessionStoreFactory._build_redis_client(),
                ttl_seconds=settings.memory_long_term_ttl_seconds,
            )
        raise ValueError(
            f"Unsupported memory_long_term_backend: {settings.memory_long_term_backend}"
        )


class MemoryExtractor:
    """Extract structured long-term memory from each turn (LLM first, keyword fallback)."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm_client = llm_client
        self.logger = logging.getLogger("pitwall.memory_extraction")

    def extract(
        self,
        *,
        user_message: str,
        assistant_message: str,
    ) -> list[ExtractedMemory]:
        if settings.memory_extraction_enabled and settings.llm_api_key:
            try:
                extracted = self._extract_with_llm(
                    user_message=user_message,
                    assistant_message=assistant_message,
                )
                if extracted:
                    return extracted
            except Exception as exc:
                self.logger.warning(
                    "memory extraction via LLM failed; fallback to keyword extraction",
                    extra={"error_type": exc.__class__.__name__},
                )
        return self._extract_keyword(user_message, assistant_message)

    def _extract_with_llm(
        self,
        *,
        user_message: str,
        assistant_message: str,
    ) -> list[ExtractedMemory]:
        client = self._get_llm_client()
        user_content = f"User: {user_message}"
        if assistant_message:
            user_content = f"{user_content}\nAssistant: {assistant_message}"
        raw = client.chat(
            messages=[
                {"role": "system", "content": MEMORY_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.05,
            max_tokens=settings.memory_extraction_max_tokens,
            timeout=settings.memory_extraction_timeout_seconds,
        )
        return self._parse_llm_result(raw)

    def _parse_llm_result(self, raw: str) -> list[ExtractedMemory]:
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        try:
            parsed = json.loads(cleaned)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("memory extraction response was not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("memory extraction response was not a JSON object")
        items = parsed.get("memories", [])
        if not isinstance(items, list):
            return []
        extracted: list[ExtractedMemory] = []
        allowed = OVERWRITE_CATEGORIES | ACCUMULATE_CATEGORIES
        for item in items:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category", "")).strip()
            key = str(item.get("key", "")).strip()
            value = " ".join(str(item.get("value", "")).split())[:240]
            if category not in allowed or not key or not value:
                continue
            extracted.append(
                ExtractedMemory(
                    category=category,
                    key=key,
                    value=value,
                    confidence=0.8,
                )
            )
        return extracted

    def _extract_keyword(
        self,
        user_message: str,
        assistant_message: str,
    ) -> list[ExtractedMemory]:
        normalized = user_message.strip()
        if not normalized:
            return []
        lowered = normalized.lower()
        content = " ".join(normalized.split())
        if len(content) > 240:
            content = content[:237].rstrip() + "..."
        if any(marker in lowered for marker in CONSTRAINT_MARKERS):
            return [
                ExtractedMemory(
                    category="constraint",
                    key="constraint",
                    value=content,
                    confidence=0.8 if assistant_message else 0.6,
                )
            ]
        if any(marker in lowered for marker in PREFERENCE_MARKERS):
            key = (
                "interest"
                if any(marker in lowered for marker in INTEREST_MARKERS)
                else "preference"
            )
            return [
                ExtractedMemory(
                    category="preference",
                    key=key,
                    value=content,
                    confidence=0.8 if assistant_message else 0.6,
                )
            ]
        return []

    def _get_llm_client(self) -> Any:
        if self.llm_client is None:
            from app.services.llm.client import LLMClient

            self.llm_client = LLMClient(model=settings.llm_model)
        return self.llm_client


class MemoryService:
    def __init__(
        self,
        store: LongTermMemoryStore | None = None,
        *,
        owner_id: str = "default",
        retriever: MemoryRetriever | None = None,
        extractor: MemoryExtractor | None = None,
    ) -> None:
        self.store = store or LongTermMemoryStoreFactory.create()
        self.owner_id = owner_id
        self.extractor = extractor or MemoryExtractor()
        if retriever is None:
            from app.services.memory_retriever import SemanticMemoryRetriever

            retriever = SemanticMemoryRetriever()
        self.retriever = retriever

    def build_context(
        self,
        *,
        session: ConversationSession,
        current_message: str,
        owner_id: str | None = None,
    ) -> MemoryContext:
        resolved_owner = self._resolve_owner(owner_id)
        recent_turns = session.history[-max(1, settings.memory_recent_turns) :]
        long_term_memories, retrieval_mode = self._retrieve_memories_with_mode(
            current_message, resolved_owner
        )

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
        rendered = self._fit_context_budget(
            rendered, current_message, recent_turns, session.summary
        )
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
            memory_retrieval_mode=retrieval_mode,
        )

    def record_interaction(
        self,
        *,
        session_id: str,
        user_message: str,
        assistant_message: str,
        owner_id: str | None = None,
    ) -> LongTermMemory | None:
        if not settings.memory_long_term_enabled:
            return None
        resolved_owner = self._resolve_owner(owner_id)

        extracted = self.extractor.extract(
            user_message=user_message,
            assistant_message=assistant_message,
        )
        if not extracted:
            return None

        memories = self._build_memories(
            extracted=extracted,
            session_id=session_id,
            owner_id=resolved_owner,
        )
        if not memories:
            return None

        first: LongTermMemory | None = None
        for memory in memories:
            self.store.save(memory)
            if first is None:
                first = memory
        return first

    def retrieve_memories(
        self, query: str, owner_id: str | None = None
    ) -> list[LongTermMemory]:
        memories, _ = self._retrieve_memories_with_mode(
            query, self._resolve_owner(owner_id)
        )
        return memories

    def _retrieve_memories_with_mode(
        self, query: str, owner_id: str
    ) -> tuple[list[LongTermMemory], str]:
        if not settings.memory_long_term_enabled:
            return [], "disabled"

        memories = self.store.list(owner_id)
        if not memories:
            return [], "disabled"

        top_k = max(0, settings.memory_long_term_top_k)
        semantic = self.retriever.retrieve(query, memories, top_k)
        if semantic is not None:
            return semantic, "semantic"
        return self._retrieve_by_keywords(query, memories, top_k), "lexical"

    def _build_memories(
        self,
        *,
        extracted: list[ExtractedMemory],
        session_id: str,
        owner_id: str,
    ) -> list[LongTermMemory]:
        memories: list[LongTermMemory] = []
        now = datetime.now(UTC)
        for item in extracted:
            category = (
                item.category
                if item.category in OVERWRITE_CATEGORIES
                or item.category in ACCUMULATE_CATEGORIES
                else "preference"
            )
            base_key = f"{category}:{self._slug(item.key) or category}"
            existing = self.store.find_by_key(owner_id, base_key) if base_key else None

            if category in OVERWRITE_CATEGORIES:
                if existing is not None:
                    memory = replace(
                        existing,
                        content=item.value,
                        memory_type=category,
                        confidence=item.confidence,
                        source_session_id=session_id,
                        updated_at=now,
                    )
                else:
                    memory = LongTermMemory(
                        memory_id=uuid4().hex,
                        content=item.value,
                        memory_type=category,
                        owner_id=owner_id,
                        confidence=item.confidence,
                        source_session_id=session_id,
                        memory_key=base_key,
                        created_at=now,
                        updated_at=now,
                    )
                memories.append(memory)
                continue

            # preference/history accumulate: same key+value is a no-op, otherwise append a new row.
            if existing is not None and existing.content == item.value:
                continue
            append_key = base_key
            if existing is not None:
                append_key = f"{base_key}:{uuid4().hex[:8]}"
            memories.append(
                LongTermMemory(
                    memory_id=uuid4().hex,
                    content=item.value,
                    memory_type=category,
                    owner_id=owner_id,
                    confidence=item.confidence,
                    source_session_id=session_id,
                    memory_key=append_key,
                    created_at=now,
                    updated_at=now,
                )
            )
        return memories

    def _resolve_owner(self, owner_id: str | None) -> str:
        resolved = (owner_id or self.owner_id).strip()
        return resolved or "default"

    def _retrieve_by_keywords(
        self,
        query: str,
        memories: list[LongTermMemory],
        top_k: int,
    ) -> list[LongTermMemory]:
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
        return [memory for _, memory in scored[:top_k]]

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
            return (
                f"{summary_section}\n\n{required}"
                if self.estimate_tokens(summary_section) <= remaining
                else required
            )
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

    @staticmethod
    def _slug(text: str) -> str:
        normalized = text.strip().lower()
        cleaned = []
        for char in normalized:
            if char.isalnum() or char in ("-", "_"):
                cleaned.append(char)
            else:
                cleaned.append("-")
        slug = "".join(cleaned).strip("-")
        return slug[:60] or "value"

    def _terms(self, text: str) -> set[str]:
        normalized = text.lower()
        ascii_terms = {
            token.strip(".,?!:;()[]")
            for token in normalized.split()
            if len(token.strip(".,?!:;()[]")) >= 3
        }
        cjk_terms = {char for char in text if "一" <= char <= "鿿"}
        return ascii_terms | cjk_terms
