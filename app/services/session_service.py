from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
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


class InMemorySessionStore:
    """内存会话存储。

    当前默认实现，后续可以替换为 Redis。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationSession] = {}

    def get(self, session_id: str) -> ConversationSession | None:
        return self._sessions.get(session_id)

    def save(self, session: ConversationSession) -> None:
        self._sessions[session.session_id] = session


class SessionStoreFactory:
    """会话存储工厂。"""

    @staticmethod
    def create() -> SessionStore:
        backend = settings.session_backend.lower()
        if backend == "memory":
            return InMemorySessionStore()

        raise ValueError(f"Unsupported session backend: {settings.session_backend}")


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
