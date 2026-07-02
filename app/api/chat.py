from fastapi import APIRouter, Query, Response

from app.schemas.chat import ChatHistoryResponse, ChatRequest, ChatResponse, ChatSessionListResponse
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
    "/{session_id}/history",
    response_model=ChatHistoryResponse,
    summary="Get stored chat history",
    description="Fetch the persisted conversation history for a session.",
)
def get_chat_history(session_id: str, response: Response) -> ChatHistoryResponse:
    response.headers["X-PitWall-Endpoint-Mode"] = "primary"
    response.headers["X-PitWall-Endpoint-Note"] = PRIMARY_ENDPOINT_NOTE
    return chat_service.get_history(session_id)
