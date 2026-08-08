import logging
import time
from collections.abc import Callable

from app.core.logging import log_structured
from app.agents.function_calling import FunctionCallingAgent
from app.agents.intent_router import IntentRouter
from app.agents.planner import LLMQueryPlanner
from app.agents.response_formatter import AgentResponseFormatter
from app.agents.runtime_graph import LangGraphAgentRuntime
from app.agents.tool_dispatcher import ToolDispatcher
from app.config.settings import settings
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
        if settings.agent_tool_protocol == "function_calling" and settings.llm_api_key:
            try:
                agent = FunctionCallingAgent(tool_dispatcher=self.tool_dispatcher, on_token=on_token)
                response = agent.run(effective_message, fallback_intent=fallback_intent)
                response.trace = self._with_latency_trace(response.trace, started_at)
                log_structured(
                    self.logger,
                    "agent_query_completed",
                    intent=response.intent,
                    tool_name=response.tool_name,
                    success=response.success,
                    runtime_mode="function_calling",
                )
                return response
            except Exception as exc:
                log_structured(
                    self.logger,
                    "function_calling_failed_fallback_manual",
                    error_type=exc.__class__.__name__,
                )
        if self.runtime is not None:
            if on_token is None:
                response = self.runtime.run(
                    effective_message,
                    fallback_intent=fallback_intent,
                )
            else:
                response = self.runtime.run(
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

        tool_plan = self.planner.plan(effective_message, fallback_intent=fallback_intent)
        steps = tool_plan.get("steps") or [tool_plan]
        if on_token is None:
            results = self.tool_dispatcher.execute_plan_steps(steps)
        else:
            results = self.tool_dispatcher.execute_plan_steps(steps, on_token=on_token)
        result = results[-1]
        # 统一 intent/action 语义：最终执行的那一步（多步时是链的末端能力）
        final_step = steps[-1] if steps else tool_plan
        intent = final_step.get("intent", tool_plan["intent"])
        if len(results) > 1:
            result.payload = {
                **result.payload,
                "step_results": [
                    {
                        "tool_name": r.tool_name,
                        "success": r.success,
                        "payload": r.payload,
                    }
                    for r in results
                ],
            }
        final_answer = self.response_formatter.build(
            message=effective_message,
            intent=intent,
            tool_name=result.tool_name,
            success=result.success,
            result={**result.payload, "tool_plan": tool_plan},
            error=result.error,
        )
        response_payload = result.payload.get("response", {})
        executed_steps = [
            {
                "step": index + 1,
                "intent": step.get("intent", "general"),
                "tool_name": executed.tool_name,
                "action": step.get("action"),
                "output_key": step.get("output_key", f"step_{index}"),
                "success": executed.success,
                "error": executed.error,
            }
            for index, (step, executed) in enumerate(zip(steps, results))
        ]
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
                "action": result.payload.get("action") or final_step.get("action") or tool_plan.get("action"),
                "params": final_step.get("params", {}) or tool_plan.get("params", {}),
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
                "plan": [
                    {
                        "output_key": step.get("output_key", f"step_{index}"),
                        "intent": step.get("intent", ""),
                        "tool_name": step.get("tool_name", ""),
                        "action": step.get("action", ""),
                    }
                    for index, step in enumerate(steps)
                ],
                "steps": executed_steps,
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
