import logging
import time

from app.core.logging import log_structured
from app.agents.intent_router import IntentRouter
from app.agents.planner import LLMQueryPlanner
from app.agents.response_formatter import AgentResponseFormatter
from app.agents.runtime_graph import LangGraphAgentRuntime
from app.agents.tool_dispatcher import ToolDispatcher
from app.schemas.agent import AgentQueryResponse


class AgentService:
    """最小 Agent 服务。"""

    def __init__(
        self,
        intent_router: IntentRouter | None = None,
        planner: LLMQueryPlanner | None = None,
        tool_dispatcher: ToolDispatcher | None = None,
        runtime: LangGraphAgentRuntime | None = None,
        response_formatter: AgentResponseFormatter | None = None,
    ) -> None:
        self.logger = logging.getLogger("pitwall.agent")
        self.intent_router = intent_router or IntentRouter()
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher()
        self.planner = planner or LLMQueryPlanner(
            intent_router=self.intent_router,
            tool_dispatcher=self.tool_dispatcher,
        )
        self.response_formatter = response_formatter or AgentResponseFormatter()
        self.runtime = runtime or self._build_default_runtime()

    def handle_query(
        self,
        message: str,
        fallback_intent: str | None = None,
        conversation_context: str | None = None,
    ) -> AgentQueryResponse:
        started_at = time.perf_counter()
        effective_message = self._build_effective_message(
            message=message,
            conversation_context=conversation_context,
        )
        log_structured(
            self.logger,
            "agent_query_received",
            has_fallback_intent=fallback_intent is not None,
            has_conversation_context=conversation_context is not None,
        )
        if self.runtime is not None:
            response = self.runtime.run(effective_message, fallback_intent=fallback_intent)
            response.trace = self._with_latency_trace(response.trace, started_at)
            log_structured(
                self.logger,
                "agent_query_completed",
                intent=response.intent,
                tool_name=response.tool_name,
                success=response.success,
                runtime_mode="langgraph",
            )
            return response

        tool_plan = self.planner.plan(effective_message, fallback_intent=fallback_intent)
        intent = tool_plan["intent"]
        result = self.tool_dispatcher.execute_plan(tool_plan)
        final_answer = self.response_formatter.build(
            message=effective_message,
            intent=intent,
            tool_name=result.tool_name,
            success=result.success,
            result={**result.payload, "tool_plan": tool_plan},
            error=result.error,
        )
        response_payload = result.payload.get("response", {})
        response = AgentQueryResponse(
            intent=intent,
            tool_name=result.tool_name,
            success=result.success,
            final_answer=final_answer,
            result={**result.payload, "tool_plan": tool_plan},
            error=result.error,
            trace={
                "intent": intent,
                "tool_name": result.tool_name,
                "action": result.payload.get("action") or tool_plan.get("action"),
                "params": tool_plan.get("params", {}),
                "success": result.success,
                "error": result.error,
                "answer_status": response_payload.get("answer_status")
                or result.payload.get("answer_status")
                or ("answered" if result.success else "error"),
                "confidence": response_payload.get("confidence") or result.payload.get("confidence"),
                "evidence_count": response_payload.get("evidence_count") or result.payload.get("evidence_count", 0),
                "source_mode": response_payload.get("source_mode") or result.payload.get("source_mode"),
                "query_type": response_payload.get("query_type") or result.payload.get("query_type"),
                "citations": response_payload.get("citations") or result.payload.get("citations", []),
                "retrieved_chunks": response_payload.get("retrieved_chunks") or result.payload.get("retrieved_chunks", []),
            },
        )
        response.trace = self._with_latency_trace(response.trace, started_at)
        log_structured(
            self.logger,
            "agent_query_completed",
            intent=response.intent,
            tool_name=response.tool_name,
            success=response.success,
            runtime_mode="fallback",
        )
        return response

    def _build_default_runtime(self) -> LangGraphAgentRuntime | None:
        try:
            return LangGraphAgentRuntime(
                intent_router=self.intent_router,
                planner=self.planner,
                tool_dispatcher=self.tool_dispatcher,
                response_formatter=self.response_formatter,
            )
        except ImportError:
            return None

    def _build_effective_message(self, *, message: str, conversation_context: str | None) -> str:
        if not conversation_context:
            return message
        if self.intent_router.looks_like_follow_up(message):
            return conversation_context

        stable_memory_context = self._extract_long_term_memory_context(conversation_context)
        if stable_memory_context:
            return f"{stable_memory_context}\n\nCurrent user message:\nUser: {message}"

        return message

    def _extract_long_term_memory_context(self, conversation_context: str) -> str | None:
        marker = "Long-term memory:"
        start = conversation_context.find(marker)
        if start == -1:
            return None

        next_section = conversation_context.find("\n\n", start)
        if next_section == -1:
            return conversation_context[start:].strip()
        return conversation_context[start:next_section].strip()

    def _with_latency_trace(self, trace: dict, started_at: float) -> dict:
        return {
            **trace,
            "latency_ms_by_stage": {
                **trace.get("latency_ms_by_stage", {}),
                "agent_total": round((time.perf_counter() - started_at) * 1000, 2),
            },
        }
