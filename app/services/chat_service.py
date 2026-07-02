from app.schemas.chat import ChatResponse
from app.services.agent_service import AgentService
from app.services.session_service import SessionService


class ChatService:
    """聊天服务。"""

    def __init__(
        self,
        agent_service: AgentService | None = None,
        session_service: SessionService | None = None,
    ) -> None:
        self.agent_service = agent_service or AgentService()
        self.session_service = session_service or SessionService()

    def handle_chat(self, message: str, session_id: str | None = None) -> ChatResponse:
        session = self.session_service.get_or_create_session(session_id)
        fallback_intent = self.session_service.get_last_intent(session.session_id)

        self.session_service.append_user_message(session.session_id, message)
        response = self.agent_service.handle_query(message, fallback_intent=fallback_intent)
        self.session_service.append_agent_response(session.session_id, response)

        return ChatResponse(
            session_id=session.session_id,
            response=response,
            history=self.session_service.get_history(session.session_id),
        )
