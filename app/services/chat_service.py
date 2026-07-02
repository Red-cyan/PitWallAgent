from app.schemas.chat import ChatHistoryResponse, ChatResponse, ChatSessionListResponse, ChatSessionSummary
from app.services.agent_service import AgentService
from app.services.context_builder import ContextBuilder
from app.services.session_service import SessionService


class ChatService:
    """聊天服务。"""

    def __init__(
        self,
        agent_service: AgentService | None = None,
        session_service: SessionService | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self.agent_service = agent_service or AgentService()
        self.session_service = session_service or SessionService()
        self.context_builder = context_builder or ContextBuilder()

    def handle_chat(self, message: str, session_id: str | None = None) -> ChatResponse:
        session = self.session_service.get_or_create_session(session_id)
        history = self.session_service.get_history(session.session_id)
        fallback_intent = self.session_service.get_last_intent(session.session_id)
        conversation_context = self.context_builder.build_context(history, message)

        self.session_service.append_user_message(session.session_id, message)
        response = self.agent_service.handle_query(
            message,
            fallback_intent=fallback_intent,
            conversation_context=conversation_context,
        )
        self.session_service.append_agent_response(session.session_id, response)

        updated_history = self.session_service.get_history(session.session_id)
        summary = self._build_summary(session.session_id, updated_history)

        return ChatResponse(
            session_id=session.session_id,
            response=response,
            history=updated_history,
            session=summary,
        )

    def get_history(self, session_id: str) -> ChatHistoryResponse:
        session = self.session_service.get_or_create_session(session_id)
        history = self.session_service.get_history(session.session_id)
        return ChatHistoryResponse(
            session=self._build_summary(session.session_id, history),
            history=history,
        )

    def list_sessions(self, limit: int = 20) -> ChatSessionListResponse:
        sessions = self.session_service.list_sessions(limit=limit)
        return ChatSessionListResponse(
            sessions=[
                self._build_summary(session.session_id, list(session.history))
                for session in sessions
            ]
        )

    def _build_summary(self, session_id: str, history: list) -> ChatSessionSummary:
        session = self.session_service.get_or_create_session(session_id)
        return ChatSessionSummary(
            session_id=session_id,
            turn_count=len(history),
            last_intent=self.session_service.get_last_intent(session_id),
            updated_at=session.updated_at,
        )
