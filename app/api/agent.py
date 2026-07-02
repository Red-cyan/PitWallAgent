from fastapi import APIRouter, Response

from app.schemas.agent import AgentQueryRequest, AgentQueryResponse
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/agent", tags=["agent"])
agent_service = AgentService()

DEBUG_ENDPOINT_NOTE = "Debug endpoint. Prefer /api/chat for session-based conversations."


@router.post(
    "/query",
    response_model=AgentQueryResponse,
    deprecated=True,
    summary="Execute a single low-level agent query",
    description=DEBUG_ENDPOINT_NOTE,
)
def query_agent(request: AgentQueryRequest, response: Response) -> AgentQueryResponse:
    response.headers["X-PitWall-Endpoint-Mode"] = "debug"
    response.headers["X-PitWall-Endpoint-Note"] = DEBUG_ENDPOINT_NOTE
    return agent_service.handle_query(request.message)
