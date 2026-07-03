import logging
import time
from collections.abc import Iterator

from app.core.logging import log_structured
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatResponse,
    ChatSessionDeleteResponse,
    ChatSessionListResponse,
    ChatSessionSummary,
)
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
        self.logger = logging.getLogger("pitwall.chat")
        self.agent_service = agent_service or AgentService()
        self.session_service = session_service or SessionService()
        self.context_builder = context_builder or ContextBuilder()

    def handle_chat(self, message: str, session_id: str | None = None) -> ChatResponse:
        session = self.session_service.get_or_create_session(session_id)
        history = self.session_service.get_history(session.session_id)
        fallback_intent = self.session_service.get_last_intent(session.session_id)
        conversation_context = self.context_builder.build_context(history, message)

        log_structured(
            self.logger,
            "chat_request_received",
            session_id=session.session_id,
            history_turn_count=len(history),
            has_fallback_intent=fallback_intent is not None,
        )

        self.session_service.append_user_message(session.session_id, message)
        response = self.agent_service.handle_query(
            message,
            fallback_intent=fallback_intent,
            conversation_context=conversation_context,
        )
        self.session_service.append_agent_response(session.session_id, response)

        updated_history = self.session_service.get_history(session.session_id)
        summary = self._build_summary(session.session_id, updated_history)

        log_structured(
            self.logger,
            "chat_response_generated",
            session_id=session.session_id,
            intent=response.intent,
            tool_name=response.tool_name,
            success=response.success,
            history_turn_count=len(updated_history),
        )

        return ChatResponse(
            session_id=session.session_id,
            response=response,
            history=updated_history,
            session=summary,
        )

    def stream_chat(self, message: str, session_id: str | None = None) -> Iterator[dict]:
        session = self.session_service.get_or_create_session(session_id)
        started_at = time.perf_counter()

        yield {
            "event": "session_started",
            "data": {"session_id": session.session_id},
        }
        yield {
            "event": "status",
            "data": {"session_id": session.session_id, "message": "thinking"},
        }
        yield {
            "event": "status",
            "data": {"session_id": session.session_id, "message": "routing"},
        }

        history = self.session_service.get_history(session.session_id)
        fallback_intent = self.session_service.get_last_intent(session.session_id)
        conversation_context = self.context_builder.build_context(history, message)

        self.session_service.append_user_message(session.session_id, message)
        yield {
            "event": "status",
            "data": {"session_id": session.session_id, "message": "retrieving"},
        }

        response_payload = self.agent_service.handle_query(
            message,
            fallback_intent=fallback_intent,
            conversation_context=conversation_context,
        )
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        response_payload.trace = {
            **response_payload.trace,
            "latency_ms_by_stage": {
                **response_payload.trace.get("latency_ms_by_stage", {}),
                "total_before_stream": elapsed_ms,
            },
        }
        self.session_service.append_agent_response(session.session_id, response_payload)

        updated_history = self.session_service.get_history(session.session_id)
        response = ChatResponse(
            session_id=session.session_id,
            response=response_payload,
            history=updated_history,
            session=self._build_summary(session.session_id, updated_history),
        )
        full_answer = response.response.final_answer

        log_structured(
            self.logger,
            "chat_stream_started",
            session_id=response.session_id,
            output_length=len(full_answer),
        )
        yield {
            "event": "status",
            "data": {"session_id": response.session_id, "message": "generating"},
        }

        for delta in self._chunk_text(full_answer):
            yield {
                "event": "message_delta",
                "data": {"session_id": response.session_id, "delta": delta},
            }
            time.sleep(0.02)

        yield {
            "event": "message_completed",
            "data": response.model_dump(mode="json"),
        }

        log_structured(
            self.logger,
            "chat_stream_completed",
            session_id=response.session_id,
            output_length=len(full_answer),
        )

    def get_history(self, session_id: str) -> ChatHistoryResponse:
        session = self.session_service.get_or_create_session(session_id)
        history = self.session_service.get_history(session.session_id)
        log_structured(
            self.logger,
            "chat_history_fetched",
            session_id=session.session_id,
            history_turn_count=len(history),
        )
        return ChatHistoryResponse(
            session=self._build_summary(session.session_id, history),
            history=history,
        )

    def list_sessions(self, limit: int = 20) -> ChatSessionListResponse:
        sessions = self.session_service.list_sessions(limit=limit)
        log_structured(
            self.logger,
            "chat_sessions_listed",
            session_count=len(sessions),
            limit=limit,
        )
        return ChatSessionListResponse(
            sessions=[
                self._build_summary(session.session_id, list(session.history))
                for session in sessions
            ]
        )

    def get_session(self, session_id: str) -> ChatSessionSummary | None:
        session = self.session_service.get_session(session_id)
        if session is None:
            log_structured(
                self.logger,
                "chat_session_missing",
                session_id=session_id,
            )
            return None
        log_structured(
            self.logger,
            "chat_session_fetched",
            session_id=session_id,
            history_turn_count=len(session.history),
        )
        return self._build_summary(session.session_id, list(session.history))

    def delete_session(self, session_id: str) -> ChatSessionDeleteResponse:
        deleted = self.session_service.delete_session(session_id)
        log_structured(
            self.logger,
            "chat_session_deleted",
            session_id=session_id,
            deleted=deleted,
        )
        return ChatSessionDeleteResponse(session_id=session_id, deleted=deleted)

    def _build_summary(self, session_id: str, history: list) -> ChatSessionSummary:
        session = self.session_service.get_or_create_session(session_id)
        return ChatSessionSummary(
            session_id=session_id,
            turn_count=len(history),
            last_intent=self.session_service.get_last_intent(session_id),
            updated_at=session.updated_at,
        )

    def _chunk_text(self, text: str, chunk_size: int = 24) -> list[str]:
        if not text:
            return [""]

        return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]
