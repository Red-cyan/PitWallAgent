from app.agents.intent_router import IntentRouter
from app.agents.tool_dispatcher import ToolDispatcher
from app.schemas.agent import AgentQueryResponse


class AgentService:
    """最小 Agent 服务。"""

    def __init__(
        self,
        intent_router: IntentRouter | None = None,
        tool_dispatcher: ToolDispatcher | None = None,
    ) -> None:
        self.intent_router = intent_router or IntentRouter()
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher()

    def handle_query(self, message: str) -> AgentQueryResponse:
        intent = self.intent_router.route(message)
        result = self.tool_dispatcher.dispatch(intent=intent, message=message)
        return AgentQueryResponse(
            intent=intent,
            tool_name=result.tool_name,
            success=result.success,
            result=result.payload,
            error=result.error,
        )
