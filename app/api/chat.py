import json

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app.schemas.chat import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionDeleteResponse,
    ChatSessionListResponse,
    ChatSessionSummary,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])
chat_service = ChatService()

PRIMARY_ENDPOINT_NOTE = "Primary conversational endpoint with session memory."


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a chat message",
    description=PRIMARY_ENDPOINT_NOTE,
)
def chat(request: ChatRequest, response: Response) -> ChatResponse:
    response.headers["X-PitWall-Endpoint-Mode"] = "primary"
    response.headers["X-PitWall-Endpoint-Note"] = PRIMARY_ENDPOINT_NOTE
    return chat_service.handle_chat(message=request.message, session_id=request.session_id)


@router.post(
    "/stream",
    summary="Send a chat message with SSE streaming",
    description=PRIMARY_ENDPOINT_NOTE,
)
def stream_chat(request: ChatRequest) -> StreamingResponse:
    def event_stream():
        try:
            for event in chat_service.stream_chat(
                message=request.message,
                session_id=request.session_id,
            ):
                yield _format_sse_event(event["event"], event["data"])
        except Exception as exc:
            yield _format_sse_event(
                "error",
                {"message": str(exc), "error_type": exc.__class__.__name__},
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-PitWall-Endpoint-Mode": "primary",
            "X-PitWall-Endpoint-Note": PRIMARY_ENDPOINT_NOTE,
        },
    )


@router.get(
    "/sessions",
    response_model=ChatSessionListResponse,
    summary="List recent chat sessions",
    description="Fetch recent chat sessions with basic metadata.",
)
def list_chat_sessions(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
) -> ChatSessionListResponse:
    response.headers["X-PitWall-Endpoint-Mode"] = "primary"
    response.headers["X-PitWall-Endpoint-Note"] = PRIMARY_ENDPOINT_NOTE
    return chat_service.list_sessions(limit=limit)


@router.get(
    "/{session_id}",
    response_model=ChatSessionSummary,
    summary="Get chat session metadata",
    description="Fetch metadata for a single chat session.",
)
def get_chat_session(session_id: str, response: Response) -> ChatSessionSummary:
    response.headers["X-PitWall-Endpoint-Mode"] = "primary"
    response.headers["X-PitWall-Endpoint-Note"] = PRIMARY_ENDPOINT_NOTE
    session = chat_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return session


@router.delete(
    "/{session_id}",
    response_model=ChatSessionDeleteResponse,
    summary="Delete a chat session",
    description="Delete a stored chat session and its metadata.",
)
def delete_chat_session(session_id: str, response: Response) -> ChatSessionDeleteResponse:
    response.headers["X-PitWall-Endpoint-Mode"] = "primary"
    response.headers["X-PitWall-Endpoint-Note"] = PRIMARY_ENDPOINT_NOTE
    result = chat_service.delete_session(session_id)
    if not result.deleted:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return result


@router.get(
    "/{session_id}/history",
    response_model=ChatHistoryResponse,
    summary="Get stored chat history",
    description="Fetch the persisted conversation history for a session.",
)
def get_chat_history(session_id: str, response: Response) -> ChatHistoryResponse:
    response.headers["X-PitWall-Endpoint-Mode"] = "primary"
    response.headers["X-PitWall-Endpoint-Note"] = PRIMARY_ENDPOINT_NOTE
    return chat_service.get_history(session_id)


def _format_sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
