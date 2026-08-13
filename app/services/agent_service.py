import logging
import time
from collections.abc import Callable

from app.agents.intent_router import IntentRouter
from app.agents.planner import LLMQueryPlanner
from app.agents.response_formatter import AgentResponseFormatter
from app.agents.runtime_graph import LangGraphAgentRuntime
from app.agents.tool_dispatcher import ToolDispatcher
from app.core.logging import log_structured
from app.schemas.agent import AgentQueryResponse


class AgentService:
    """Application service backed exclusively by the LangGraph runtime."""

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
        return self._handle_query(
            message,
            fallback_intent=fallback_intent,
            conversation_context=conversation_context,
        )

    def stream_query(
        self,
        message: str,
        *,
        on_token: Callable[[str], None],
        fallback_intent: str | None = None,
        conversation_context: str | None = None,
    ) -> AgentQueryResponse:
        return self._handle_query(
            message,
            fallback_intent=fallback_intent,
            conversation_context=conversation_context,
            on_token=on_token,
        )

    def _handle_query(
        self,
        message: str,
        *,
        fallback_intent: str | None = None,
        conversation_context: str | None = None,
        on_token: Callable[[str], None] | None = None,
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
        runtime = self.runtime
        if runtime is None:
            runtime = self._build_default_runtime()
            self.runtime = runtime
        if on_token is None:
            response = runtime.run(effective_message, fallback_intent=fallback_intent)
        else:
            response = runtime.run(
                effective_message,
                fallback_intent=fallback_intent,
                on_token=on_token,
            )
        response.trace = self._with_latency_trace(response.trace, started_at)
        steps = response.trace.get("steps")
        log_structured(
            self.logger,
            "agent_query_completed",
            intent=response.intent,
            tool_name=response.tool_name,
            success=response.success,
            runtime_mode="langgraph",
            react_steps=len(steps) if isinstance(steps, list) else 0,
            judge_outcome=response.trace.get("judge_outcome"),
        )
        return response

    def _build_default_runtime(self) -> LangGraphAgentRuntime:
        return LangGraphAgentRuntime(
            intent_router=self.intent_router,
            planner=self.planner,
            tool_dispatcher=self.tool_dispatcher,
            response_formatter=self.response_formatter,
        )

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
