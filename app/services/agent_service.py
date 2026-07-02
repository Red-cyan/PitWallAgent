from app.agents.intent_router import IntentRouter
from app.agents.response_formatter import AgentResponseFormatter
from app.agents.runtime_graph import LangGraphAgentRuntime
from app.agents.tool_dispatcher import ToolDispatcher
from app.schemas.agent import AgentQueryResponse


class AgentService:
    """最小 Agent 服务。"""

    def __init__(
        self,
        intent_router: IntentRouter | None = None,
        tool_dispatcher: ToolDispatcher | None = None,
        runtime: LangGraphAgentRuntime | None = None,
        response_formatter: AgentResponseFormatter | None = None,
    ) -> None:
        self.intent_router = intent_router or IntentRouter()
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher()
        self.response_formatter = response_formatter or AgentResponseFormatter()
        self.runtime = runtime or self._build_default_runtime()

    def handle_query(self, message: str, fallback_intent: str | None = None) -> AgentQueryResponse:
        if self.runtime is not None:
            return self.runtime.run(message, fallback_intent=fallback_intent)

        intent = self.intent_router.route(message, fallback_intent=fallback_intent)
        result = self.tool_dispatcher.dispatch(intent=intent, message=message)
        final_answer = self.response_formatter.build(
            message=message,
            intent=intent,
            tool_name=result.tool_name,
            success=result.success,
            result=result.payload,
            error=result.error,
        )
        return AgentQueryResponse(
            intent=intent,
            tool_name=result.tool_name,
            success=result.success,
            final_answer=final_answer,
            result=result.payload,
            error=result.error,
        )

    def _build_default_runtime(self) -> LangGraphAgentRuntime | None:
        try:
            return LangGraphAgentRuntime(
                intent_router=self.intent_router,
                tool_dispatcher=self.tool_dispatcher,
                response_formatter=self.response_formatter,
            )
        except ImportError:
            return None
