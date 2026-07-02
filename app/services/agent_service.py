from app.agents.intent_router import IntentRouter
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
    ) -> None:
        self.intent_router = intent_router or IntentRouter()
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher()
        self.runtime = runtime or self._build_default_runtime()

    def handle_query(self, message: str) -> AgentQueryResponse:
        if self.runtime is not None:
            return self.runtime.run(message)

        intent = self.intent_router.route(message)
        result = self.tool_dispatcher.dispatch(intent=intent, message=message)
        final_answer = self._build_fallback_final_answer(intent=intent, result=result.payload, success=result.success, error=result.error)
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
            )
        except ImportError:
            return None

    def _build_fallback_final_answer(
        self,
        intent: str,
        result: dict,
        success: bool,
        error: str | None,
    ) -> str:
        if not success:
            return error or "请求处理失败。"
        if intent == "regulation":
            return result.get("response", {}).get("answer", "已完成规则查询。")
        if intent == "news":
            return "已完成新闻查询。"
        if intent == "race":
            return "已完成比赛信息查询。"
        return "已完成请求处理。"
