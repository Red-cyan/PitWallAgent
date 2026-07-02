from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import uuid4

from app.config.settings import settings
from app.schemas.agent import AgentQueryResponse
from app.schemas.chat import ConversationTurn


@dataclass
class ConversationSession:
    """会话状态。"""

    session_id: str
    history: list[ConversationTurn] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SessionStore(Protocol):
    """会话存储接口。"""

    def get(self, session_id: str) -> ConversationSession | None:
        """按 ID 获取会话。"""

    def save(self, session: ConversationSession) -> None:
        """保存会话。"""

    def list_sessions(self, limit: int = 20) -> list[ConversationSession]:
        """列出最近更新的会话。"""

    def delete(self, session_id: str) -> bool:
        """删除会话。"""


class RedisClientProtocol(Protocol):
    """Redis 客户端最小协议。"""

    def get(self, key: str) -> str | bytes | None:
        """读取键值。"""

    def setex(self, key: str, time: int, value: str) -> Any:
        """写入带 TTL 的键值。"""

    def zadd(self, key: str, mapping: dict[str, float]) -> Any:
        """向有序集合写入分值。"""

    def zrevrange(self, key: str, start: int, end: int) -> list[str] | list[bytes]:
        """按分值倒序读取有序集合。"""

    def delete(self, key: str) -> int:
        """删除键。"""

    def zrem(self, key: str, *members: str) -> int:
        """从有序集合移除成员。"""


class InMemorySessionStore:
    """内存会话存储。"""

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationSession] = {}

    def get(self, session_id: str) -> ConversationSession | None:
        return self._sessions.get(session_id)

    def save(self, session: ConversationSession) -> None:
        self._sessions[session.session_id] = session

    def list_sessions(self, limit: int = 20) -> list[ConversationSession]:
        sessions = sorted(
            self._sessions.values(),
            key=lambda session: session.updated_at,
            reverse=True,
        )
        return sessions[:limit]

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None


class RedisSessionStore:
    """Redis 会话存储。"""

    KEY_PREFIX = "pitwall:session:"
    SESSION_INDEX_KEY = "pitwall:sessions:index"

    def __init__(
        self,
        client: RedisClientProtocol,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds or settings.session_ttl_seconds

    def get(self, session_id: str) -> ConversationSession | None:
        payload = self.client.get(self._build_key(session_id))
        if payload is None:
            return None

        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")

        return self._deserialize_session(payload)

    def save(self, session: ConversationSession) -> None:
        self.client.setex(
            self._build_key(session.session_id),
            self.ttl_seconds,
            self._serialize_session(session),
        )
        self.client.zadd(
            self.SESSION_INDEX_KEY,
            {session.session_id: session.updated_at.timestamp()},
        )

    def list_sessions(self, limit: int = 20) -> list[ConversationSession]:
        session_ids = self.client.zrevrange(self.SESSION_INDEX_KEY, 0, max(limit - 1, 0))
        sessions: list[ConversationSession] = []
        for session_id in session_ids:
            if isinstance(session_id, bytes):
                session_id = session_id.decode("utf-8")
            session = self.get(session_id)
            if session is not None:
                sessions.append(session)
        return sessions

    def delete(self, session_id: str) -> bool:
        removed = self.client.delete(self._build_key(session_id))
        self.client.zrem(self.SESSION_INDEX_KEY, session_id)
        return removed > 0

    def _build_key(self, session_id: str) -> str:
        return f"{self.KEY_PREFIX}{session_id}"

    def _serialize_session(self, session: ConversationSession) -> str:
        payload = {
            "session_id": session.session_id,
            "updated_at": session.updated_at.isoformat(),
            "history": [turn.model_dump(mode="json") for turn in session.history],
        }
        return json.dumps(payload, ensure_ascii=False)

    def _deserialize_session(self, payload: str) -> ConversationSession:
        data = json.loads(payload)
        return ConversationSession(
            session_id=data["session_id"],
            updated_at=datetime.fromisoformat(data["updated_at"]).astimezone(UTC),
            history=[ConversationTurn.model_validate(turn) for turn in data.get("history", [])],
        )


class SessionStoreFactory:
    """会话存储工厂。"""

    @staticmethod
    def create() -> SessionStore:
        backend = settings.session_backend.lower()
        if backend == "memory":
            return InMemorySessionStore()
        if backend == "redis":
            return RedisSessionStore(
                client=SessionStoreFactory._build_redis_client(),
                ttl_seconds=settings.session_ttl_seconds,
            )

        raise ValueError(f"Unsupported session backend: {settings.session_backend}")

    @staticmethod
    def _build_redis_client() -> RedisClientProtocol:
        try:
            from redis import Redis
        except ImportError as exc:
            raise ImportError("redis package is required when session_backend=redis.") from exc

        return cast(RedisClientProtocol, Redis.from_url(settings.resolved_redis_url, decode_responses=True))


class SessionService:
    """会话服务。"""

    def __init__(self, store: SessionStore | None = None) -> None:
        self.store = store or SessionStoreFactory.create()

    def get_or_create_session(self, session_id: str | None = None) -> ConversationSession:
        resolved_session_id = session_id or self._generate_session_id()
        session = self.store.get(resolved_session_id)
        if session is None:
            session = ConversationSession(session_id=resolved_session_id)
            self.store.save(session)
        return session

    def get_session(self, session_id: str) -> ConversationSession | None:
        return self.store.get(session_id)

    def append_user_message(self, session_id: str, message: str) -> ConversationTurn:
        session = self.get_or_create_session(session_id)
        turn = ConversationTurn(
            role="user",
            message=message,
            created_at=datetime.now(UTC),
        )
        self._append_turn(session, turn)
        return turn

    def append_agent_response(self, session_id: str, response: AgentQueryResponse) -> ConversationTurn:
        session = self.get_or_create_session(session_id)
        turn = ConversationTurn(
            role="assistant",
            message=response.final_answer,
            created_at=datetime.now(UTC),
            intent=response.intent,
            tool_name=response.tool_name,
        )
        self._append_turn(session, turn)
        return turn

    def get_history(self, session_id: str) -> list[ConversationTurn]:
        session = self.get_or_create_session(session_id)
        return list(session.history)

    def list_sessions(self, limit: int = 20) -> list[ConversationSession]:
        return self.store.list_sessions(limit=limit)

    def delete_session(self, session_id: str) -> bool:
        return self.store.delete(session_id)

    def get_last_intent(self, session_id: str) -> str | None:
        session = self.store.get(session_id)
        if session is None:
            return None

        for turn in reversed(session.history):
            if turn.role == "assistant" and turn.intent:
                return turn.intent

        return None

    def _append_turn(self, session: ConversationSession, turn: ConversationTurn) -> None:
        session.history.append(turn)
        session.updated_at = turn.created_at

        max_turns = settings.session_history_max_turns
        if max_turns > 0 and len(session.history) > max_turns:
            session.history = session.history[-max_turns:]

        self.store.save(session)

    def _generate_session_id(self) -> str:
        return uuid4().hex
