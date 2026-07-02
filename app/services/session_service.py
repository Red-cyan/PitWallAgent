from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.agent import AgentQueryResponse
from app.schemas.chat import ConversationTurn


@dataclass
class ConversationSession:
    """会话状态。"""

    session_id: str
    history: list[ConversationTurn] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SessionService:
    """会话服务。

    当前使用内存存储，后续可以平滑替换为 Redis。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationSession] = {}

    def get_or_create_session(self, session_id: str | None = None) -> ConversationSession:
        resolved_session_id = session_id or self._generate_session_id()
        session = self._sessions.get(resolved_session_id)
        if session is None:
            session = ConversationSession(session_id=resolved_session_id)
            self._sessions[resolved_session_id] = session
        return session

    def append_user_message(self, session_id: str, message: str) -> ConversationTurn:
        session = self.get_or_create_session(session_id)
        turn = ConversationTurn(
            role="user",
            message=message,
            created_at=datetime.now(UTC),
        )
        session.history.append(turn)
        session.updated_at = turn.created_at
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
        session.history.append(turn)
        session.updated_at = turn.created_at
        return turn

    def get_history(self, session_id: str) -> list[ConversationTurn]:
        session = self.get_or_create_session(session_id)
        return list(session.history)

    def get_last_intent(self, session_id: str) -> str | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None

        for turn in reversed(session.history):
            if turn.role == "assistant" and turn.intent:
                return turn.intent

        return None

    def _generate_session_id(self) -> str:
        return uuid4().hex
