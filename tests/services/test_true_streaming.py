from typing import Any, cast

from app.schemas.agent import AgentQueryResponse
from app.services.chat_service import ChatService
from app.services.general_answer_service import GeneralAnswerService
from app.services.session_service import SessionService


class StreamingAgentService:
    def stream_query(self, message: str, *, on_token, **kwargs) -> AgentQueryResponse:
        for token in ("real ", "tokens"):
            on_token(token)
        return AgentQueryResponse(
            intent="general",
            tool_name="general_tool",
            success=True,
            final_answer="real tokens",
            result={"response": {"answer": "real tokens"}},
            trace={"answer_status": "answered"},
        )


class StreamingLLMClient:
    def stream_chat(self, **kwargs):
        yield "Senna "
        yield "was exceptional."


def test_chat_service_emits_provider_tokens_and_persists_once() -> None:
    sessions = SessionService()
    service = ChatService(
        agent_service=cast(Any, StreamingAgentService()),
        session_service=sessions,
    )

    events = list(service.stream_chat("Why was Senna exceptional?", session_id="stream-session"))

    deltas = [event["data"]["delta"] for event in events if event["event"] == "message_delta"]
    completed = next(event for event in events if event["event"] == "message_completed")
    assert deltas == ["real ", "tokens"]
    assert completed["data"]["response"]["trace"]["stream_mode"] == "token"
    assert completed["data"]["session"]["title"] == "Why was Senna exceptional?"
    assert [turn.role for turn in sessions.get_history("stream-session")] == ["user", "assistant"]


def test_closing_stream_before_completion_does_not_persist_assistant() -> None:
    sessions = SessionService()
    service = ChatService(
        agent_service=cast(Any, StreamingAgentService()),
        session_service=sessions,
    )
    stream = service.stream_chat("Stop this answer", session_id="cancel-session")

    while next(stream)["event"] != "message_delta":
        pass
    stream.close()

    assert [turn.role for turn in sessions.get_history("cancel-session")] == ["user"]


def test_general_answer_forwards_real_stream_tokens() -> None:
    tokens: list[str] = []
    service = GeneralAnswerService(llm_client=cast(Any, StreamingLLMClient()))

    response = service.answer("Why was Senna exceptional?", on_token=tokens.append)

    assert tokens == ["Senna ", "was exceptional."]
    assert response["answer"] == "Senna was exceptional."
    assert response["mode"] == "llm"
