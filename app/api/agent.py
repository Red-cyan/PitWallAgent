from fastapi import APIRouter

from app.schemas.agent import AgentQueryRequest, AgentQueryResponse
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/agent", tags=["agent"])
agent_service = AgentService()


@router.post("/query", response_model=AgentQueryResponse)
def query_agent(request: AgentQueryRequest) -> AgentQueryResponse:
    return agent_service.handle_query(request.message)
