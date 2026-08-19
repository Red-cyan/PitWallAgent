from __future__ import annotations

import logging
import operator
import threading
import uuid
from collections.abc import Callable
from typing import Annotated, Any, TypeVar, TypedDict, cast

from app.agents.function_calling import (
    SYSTEM_PROMPT,
    ToolCallingModelAdapter,
    invalid_tool_result,
)
from app.agents.intent_router import IntentRouter
from app.agents.planner import LLMQueryPlanner
from app.agents.reflector import ReActReflector
from app.agents.response_formatter import AgentResponseFormatter
from app.agents.tool_dispatcher import ToolDispatcher, interpolate_params
from app.agents.tool_observation import (
    PREVIOUS_OBSERVATIONS_PREFIX,
    observation_json,
    previous_observations_message,
)
from app.config.settings import settings
from app.schemas.agent import AgentQueryResponse
from app.tools.base import ToolResult

T = TypeVar("T")


class AgentState(TypedDict, total=False):
    """Serializable state shared by both planner modes."""

    message: str
    fallback_intent: str | None
    planner_mode: str
    requested_planner_mode: str
    planner_fallback: str | None
    messages: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, Any]]
    current_batch_plans: list[dict[str, Any]]
    batch_results: list[dict[str, Any]]
    model_content: str
    tool_plan: dict[str, Any]
    plan_steps: list[dict[str, Any]]
    step_index: int
    step_outputs: dict[str, dict[str, Any]]
    intent: str
    tool_name: str
    success: bool
    result: dict[str, Any]
    error: str | None
    last_tool_answer: str
    final_answer: str
    finalization_mode: str
    max_steps_reached: bool
    trace: dict[str, Any]
    judgement: dict[str, Any]
    judge_reasons: Annotated[list[str], operator.add]
    steps: Annotated[list[dict[str, Any]], operator.add]
    step_count: int
    max_steps: int
    tool_observation_chars: int
    tool_observation_original_chars: int
    message_history_chars: int
    message_history_compacted: bool
    context_compaction_count: int


class LangGraphAgentRuntime:
    """The single orchestration runtime for structured and native tool-calling planners."""

    _token_holder = threading.local()
    _TOOL_TO_INTENT = {
        "news_tool": "news",
        "race_tool": "race",
        "regulation_tool": "regulation",
        "strategy_tool": "strategy",
        "general_tool": "general",
    }

    def __init__(
        self,
        intent_router: IntentRouter | None = None,
        planner: LLMQueryPlanner | None = None,
        tool_dispatcher: ToolDispatcher | None = None,
        response_formatter: AgentResponseFormatter | None = None,
        reflector: ReActReflector | None = None,
        tool_calling_adapter: ToolCallingModelAdapter | None = None,
        planner_mode: str | None = None,
        checkpointer: Any = None,
        max_steps: int | None = None,
    ) -> None:
        self.logger = logging.getLogger("pitwall.runtime")
        self.intent_router = intent_router or IntentRouter()
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher()
        self.planner = planner or LLMQueryPlanner(
            intent_router=self.intent_router,
            tool_dispatcher=self.tool_dispatcher,
        )
        self.response_formatter = response_formatter or AgentResponseFormatter()
        self.reflector = reflector or ReActReflector()
        self.tool_calling_adapter = tool_calling_adapter or ToolCallingModelAdapter()
        configured_mode = planner_mode or settings.agent_planner_mode
        self.planner_mode = configured_mode if configured_mode in {"structured", "tool_calling"} else "tool_calling"
        self.checkpointer = checkpointer if checkpointer is not None else self._build_default_checkpointer()
        self.max_steps = max_steps if max_steps is not None else settings.agent_react_max_steps
        self.max_parallel_tool_calls = settings.agent_max_parallel_tool_calls
        self.graph = self._build_graph()

    def run(
        self,
        message: str,
        fallback_intent: str | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> AgentQueryResponse:
        self._set_current_on_token(on_token)
        try:
            config = None
            if self.checkpointer is not None:
                from langchain_core.runnables import RunnableConfig

                config = cast(
                    RunnableConfig,
                    {
                        "configurable": {"thread_id": uuid.uuid4().hex},
                        # 结构化模式每步消耗多个 superstep（plan→tool→normalize→judge），
                        # 默认 25 的 recursion_limit 在长计划下会提前抛 GraphRecursionError。
                        "recursion_limit": max(25, (self.max_steps + 2) * 8),
                    },
                )
            state = self.graph.invoke(
                {
                    "message": message,
                    "fallback_intent": fallback_intent,
                    "planner_mode": self.planner_mode,
                    "step_count": 0 if self.planner_mode == "tool_calling" else 1,
                    "max_steps": self.max_steps,
                    "judge_reasons": [],
                    "steps": [],
                },
                config=config,
            )
        except Exception as exc:
            # 节点内任何未预期异常都不应穿透成裸 500；记录后返回降级响应。
            self.logger.error(
                "graph_invoke_failed",
                extra={"error_type": exc.__class__.__name__},
            )
            return AgentQueryResponse(
                intent="general",
                tool_name="general_tool",
                success=False,
                final_answer="抱歉，处理你的请求时出现了内部错误，请稍后重试。",
                result={},
                error=f"graph_invoke_error:{exc.__class__.__name__}",
                trace={"runtime": "langgraph", "graph_error": exc.__class__.__name__},
            )
        finally:
            self._set_current_on_token(None)

        return AgentQueryResponse(
            intent=state.get("intent", "general"),
            tool_name=state.get("tool_name", "general_tool"),
            success=state.get("success", True),
            final_answer=state["final_answer"],
            result=state.get("result", {}),
            error=state.get("error"),
            trace=state.get("trace", {}),
        )

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise ImportError("langgraph is required to build LangGraphAgentRuntime.") from exc

        graph = StateGraph(AgentState)
        graph.add_node("initialize", self._initialize_node)
        graph.add_node("model", self._model_node)
        graph.add_node("structured_plan", self._structured_plan_node)
        graph.add_node("tool_batch", self._tool_batch_node)
        graph.add_node("normalize_observation", self._normalize_observation_node)
        graph.add_node("judge", self._judge_node)
        graph.add_node("finalize", self._finalize_node)
        graph.add_node("forced_summary", self._forced_summary_node)

        graph.add_edge(START, "initialize")
        graph.add_conditional_edges(
            "initialize",
            self._route_planner,
            {"model": "model", "structured_plan": "structured_plan"},
        )
        graph.add_conditional_edges(
            "model",
            self._route_after_model,
            {"tool_batch": "tool_batch", "structured_plan": "structured_plan", "finalize": "finalize"},
        )
        graph.add_edge("structured_plan", "tool_batch")
        graph.add_edge("tool_batch", "normalize_observation")
        graph.add_edge("normalize_observation", "judge")
        graph.add_conditional_edges(
            "judge",
            self._route_after_judge,
            {
                "tool_batch": "tool_batch",
                "structured_plan": "structured_plan",
                "model": "model",
                "finalize": "finalize",
                "forced_summary": "forced_summary",
            },
        )
        graph.add_edge("forced_summary", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile(checkpointer=self.checkpointer)

    def _initialize_node(self, state: AgentState) -> AgentState:
        message = self._require(state, "message", str)
        mode = state.get("planner_mode", self.planner_mode)
        return {
            "message": message,
            "fallback_intent": state.get("fallback_intent"),
            "planner_mode": mode,
            "requested_planner_mode": mode,
            "planner_fallback": None,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            "pending_tool_calls": [],
            "current_batch_plans": [],
            "batch_results": [],
            "step_outputs": {},
            "step_count": state.get("step_count", 0 if mode == "tool_calling" else 1),
            "max_steps": state.get("max_steps", self.max_steps),
            "max_steps_reached": False,
            "finalization_mode": "direct",
            "tool_observation_chars": 0,
            "tool_observation_original_chars": 0,
            "message_history_chars": 0,
            "message_history_compacted": False,
            "context_compaction_count": 0,
        }

    def _route_planner(self, state: AgentState) -> str:
        return "model" if state.get("planner_mode") == "tool_calling" else "structured_plan"

    def _model_node(self, state: AgentState) -> AgentState:
        messages, compacted, compaction_count = self._compact_messages(state.get("messages", []), state)
        history_chars = self._messages_chars(messages)
        try:
            reply = self.tool_calling_adapter.invoke(messages)
        except Exception as exc:
            self.logger.error("tool_calling_model_failed", extra={"error_type": exc.__class__.__name__})
            return {
                "planner_mode": "structured",
                "planner_fallback": f"tool_calling_error:{exc.__class__.__name__}",
                "pending_tool_calls": [],
                "model_content": "",
                "step_count": 1,
                "messages": messages,
                "message_history_chars": history_chars,
                "message_history_compacted": compacted,
                "context_compaction_count": compaction_count,
            }

        tool_calls = list(reply.tool_calls or [])[: self.max_parallel_tool_calls]
        if not tool_calls:
            return {
                "messages": messages,
                "model_content": reply.content or "",
                "pending_tool_calls": [],
                "judge_reasons": ["complete"],
                "message_history_chars": history_chars,
                "message_history_compacted": compacted,
                "context_compaction_count": compaction_count,
            }

        pending: list[dict[str, Any]] = []
        plans: list[dict[str, Any]] = []
        for raw_call in tool_calls:
            call = cast(Any, raw_call)
            plan, validation_error = self.tool_calling_adapter.tool_call_to_plan(call)
            pending.append(
                {
                    "id": call.id,
                    "name": call.function.name,
                    "arguments": call.function.arguments or "{}",
                    "validation_error": validation_error,
                }
            )
            plans.append(plan)
        # assistant 消息只保留实际执行的 tool_calls（截断后的子集），
        # 避免出现无对应 tool 响应的孤儿 tool_call 污染对话协议。
        assistant_msg = {
            "role": "assistant",
            "content": reply.content or "",
            "tool_calls": [call.model_dump() for call in tool_calls],
        }
        return {
            "messages": [*messages, assistant_msg],
            "pending_tool_calls": pending,
            "current_batch_plans": plans,
            "model_content": "",
            "message_history_chars": history_chars,
            "message_history_compacted": compacted,
            "context_compaction_count": compaction_count,
        }

    def _route_after_model(self, state: AgentState) -> str:
        if state.get("planner_mode") == "structured":
            return "structured_plan"
        if state.get("pending_tool_calls"):
            return "tool_batch"
        return "finalize"

    def _structured_plan_node(self, state: AgentState) -> AgentState:
        message = self._require(state, "message", str)
        plan_steps = state.get("plan_steps") or []
        step_index = state.get("step_index", 0)
        judgement = state.get("judgement") or {}
        next_plan = judgement.get("next_plan")
        state_update: AgentState = {}

        if isinstance(next_plan, dict) and next_plan.get("_continue"):
            step_index += 1
        elif isinstance(next_plan, dict):
            plan_steps = [self._to_step(next_plan)]
            step_index = 0
        elif not plan_steps:
            try:
                tool_plan = self.planner.plan(message, fallback_intent=state.get("fallback_intent"))
            except Exception as exc:
                self.logger.error("structured_planner_failed", extra={"error_type": exc.__class__.__name__})
                tool_plan = {
                    "intent": "general",
                    "tool_name": "general_tool",
                    "action": "answer",
                    "params": {"question": message},
                }
            plan_steps = tool_plan.get("steps") or [self._to_step(tool_plan)]
            step_index = 0
            state_update = {"tool_plan": tool_plan, "intent": tool_plan.get("intent", "general")}

        step = plan_steps[step_index]
        params = interpolate_params(step.get("params", {}), state.get("step_outputs", {}))
        plan = {
            "intent": step.get("intent", state.get("intent", "general")),
            "tool_name": step["tool_name"],
            "action": step["action"],
            "params": params,
            "output_key": step.get("output_key", f"step_{step_index}"),
        }
        return {
            **state_update,
            "plan_steps": plan_steps,
            "step_index": step_index,
            "current_batch_plans": [plan],
            "pending_tool_calls": [],
        }

    def _tool_batch_node(self, state: AgentState) -> AgentState:
        plans = state.get("current_batch_plans", [])
        pending = state.get("pending_tool_calls", [])
        is_native = state.get("planner_mode") == "tool_calling"
        step_count = state.get("step_count", 0)
        if is_native:
            step_count += 1

        results: list[ToolResult] = []
        result_records: list[dict[str, Any]] = []
        step_outputs = dict(state.get("step_outputs", {}))
        messages = list(state.get("messages", []))
        last_tool_answer = state.get("last_tool_answer", "")
        step_records: list[dict[str, Any]] = []
        observation_chars_total = state.get("tool_observation_chars", 0)
        observation_original_chars_total = state.get("tool_observation_original_chars", 0)

        for index, plan in enumerate(plans):
            validation_error = pending[index].get("validation_error") if index < len(pending) else None
            if validation_error:
                result = invalid_tool_result(plan, validation_error)
            else:
                allow_tool_streaming = state.get("requested_planner_mode") == "structured"
                on_token = self._current_on_token() if allow_tool_streaming else None
                if on_token is None:
                    result = self.tool_dispatcher.execute_plan(plan)
                else:
                    result = self.tool_dispatcher.execute_plan(plan, on_token=on_token)
            results.append(result)
            output_key = plan.get("output_key") or plan.get("tool_call_id") or f"step_{len(state.get('steps', [])) + index}"
            step_outputs[output_key] = {
                "success": result.success,
                "payload": result.payload,
                "error": result.error,
            }
            answer = self._extract_tool_answer(result.payload) if result.success else ""
            if answer:
                last_tool_answer = answer
            step_records.append(
                {
                    "step": step_count if is_native else max(step_count, state.get("step_index", 0) + 1),
                    "intent": plan.get("intent", "general"),
                    "tool_name": result.tool_name,
                    "action": plan.get("action"),
                    "output_key": output_key,
                    "success": result.success,
                    "error": result.error,
                }
            )
            result_records.append(
                {"tool_name": result.tool_name, "success": result.success, "payload": result.payload, "error": result.error}
            )
            if is_native:
                call_id = plan.get("tool_call_id") or (pending[index].get("id") if index < len(pending) else output_key)
                content, observation_chars, original_chars = observation_json(
                    result.payload,
                    success=result.success,
                    error=result.error,
                )
                messages.append(
                    {"role": "tool", "tool_call_id": call_id, "content": content}
                )
                observation_chars_total += observation_chars
                observation_original_chars_total += original_chars

        last_result = results[-1] if results else ToolResult(tool_name="unknown", success=False, error="No tool calls.")
        last_plan = plans[-1] if plans else {}
        return {
            "messages": messages,
            "pending_tool_calls": [],
            "batch_results": result_records,
            "step_outputs": step_outputs,
            "intent": last_plan.get("intent", state.get("intent", "general")),
            "tool_name": last_result.tool_name,
            "success": all(result.success for result in results) if results else False,
            "result": last_result.payload,
            "error": next((result.error for result in results if not result.success), None),
            "last_tool_answer": last_tool_answer,
            "step_count": step_count,
            "steps": step_records,
            "tool_observation_chars": observation_chars_total,
            "tool_observation_original_chars": observation_original_chars_total,
        }

    def _normalize_observation_node(self, state: AgentState) -> AgentState:
        result = dict(state.get("result", {}))
        batch_results = state.get("batch_results", [])
        if len(batch_results) > 1:
            result["batch_results"] = batch_results
            citations: list[Any] = []
            retrieved_chunks: list[Any] = []
            evidence_count = 0
            for item in batch_results:
                payload = item.get("payload") or {}
                response = payload.get("response") or {}
                item_citations = response.get("citations") or payload.get("citations") or []
                item_chunks = response.get("retrieved_chunks") or payload.get("retrieved_chunks") or []
                if isinstance(item_citations, list):
                    citations.extend(item_citations)
                if isinstance(item_chunks, list):
                    retrieved_chunks.extend(item_chunks)
                count = response.get("evidence_count") or payload.get("evidence_count") or 0
                if isinstance(count, int):
                    evidence_count += count
            result["citations"] = citations
            result["retrieved_chunks"] = retrieved_chunks
            result["evidence_count"] = evidence_count
        return {"result": result}

    def _judge_node(self, state: AgentState) -> AgentState:
        plan_steps = state.get("plan_steps") or []
        step_index = state.get("step_index", 0)
        has_remaining = state.get("planner_mode") == "structured" and step_index + 1 < len(plan_steps)
        step_count = state.get("step_count", 0)
        max_steps = state.get("max_steps", self.max_steps)

        # max_steps 优先于继续计划：多步计划不得绕过步数上限。
        if step_count >= max_steps:
            judgement = {"finish": True, "reason": "max_steps_reached", "next_plan": None}
        elif has_remaining and state.get("success") is True:
            judgement = {"finish": False, "reason": "continue_plan", "next_plan": {"_continue": True}}
        elif self._should_judge(state):
            if not self.reflector.enabled:
                judgement = {"finish": True, "reason": "judge_disabled", "next_plan": None}
            else:
                try:
                    judgement = self.reflector.judge(
                        message=self._require(state, "message", str),
                        intent=state.get("intent", "general"),
                        tool_plan=(state.get("current_batch_plans") or [state.get("tool_plan", {})])[-1],
                        tool_result=self._build_tool_result(state),
                        step_count=step_count,
                        max_steps=max_steps,
                    )
                except Exception as exc:
                    self.logger.error("judge_result_failed", extra={"error_type": exc.__class__.__name__})
                    judgement = {"finish": True, "reason": "judge_error", "next_plan": None}
        else:
            judgement = {
                "finish": state.get("planner_mode") != "tool_calling",
                "reason": "continue" if state.get("planner_mode") == "tool_calling" else "no_judge_needed",
                "next_plan": None,
            }

        update: AgentState = {"judgement": judgement, "judge_reasons": [judgement["reason"]]}
        next_plan = judgement.get("next_plan")
        if state.get("planner_mode") == "structured" and isinstance(next_plan, dict):
            # 结构化模式下继续执行或修复都会消耗一个步数预算，防止长计划绕过上限。
            update["step_count"] = step_count + 1
            if not next_plan.get("_continue"):
                update["current_batch_plans"] = [
                    {**next_plan, "output_key": f"repair_{step_count + 1}"}
                ]
        if judgement["reason"] == "max_steps_reached":
            update["max_steps_reached"] = True
        return update

    def _route_after_judge(self, state: AgentState) -> str:
        judgement = state.get("judgement") or {}
        next_plan = judgement.get("next_plan")
        if judgement.get("reason") == "max_steps_reached":
            return "forced_summary"
        # tool_calling 模式：任何未完成的继续/修复都回到模型，由 LLM 重新生成
        # 工具调用，避免用假 tool_call_id 追加孤儿 tool 消息破坏对话协议。
        if state.get("planner_mode") == "tool_calling" and not judgement.get("finish", True):
            return "model"
        if isinstance(next_plan, dict) and not judgement.get("finish", True):
            if next_plan.get("_continue"):
                return "structured_plan"
            return "tool_batch"
        return "finalize"

    def _forced_summary_node(self, state: AgentState) -> AgentState:
        final_answer = ""
        mode = "forced_summary"
        if state.get("planner_mode") == "tool_calling":
            try:
                final_answer = self.tool_calling_adapter.summarize(state.get("messages", []))
            except Exception as exc:
                self.logger.error("forced_summary_failed", extra={"error_type": exc.__class__.__name__})
        if not final_answer:
            final_answer = state.get("last_tool_answer", "")
            mode = "tool_result_fallback" if final_answer else "empty_fallback"
        return {"final_answer": final_answer, "finalization_mode": mode, "max_steps_reached": True}

    def _finalize_node(self, state: AgentState) -> AgentState:
        final_answer = state.get("final_answer", "")
        mode = state.get("finalization_mode", "direct")
        result = dict(state.get("result", {}))
        tool_plan = state.get("tool_plan", {})

        if not final_answer and state.get("planner_mode") == "tool_calling":
            final_answer = state.get("model_content", "").strip()
        if not final_answer and state.get("planner_mode") == "structured":
            result["tool_plan"] = tool_plan
            if len(state.get("plan_steps", [])) > 1:
                result["step_results"] = self._structured_step_results(state)
            final_answer = self.response_formatter.build(
                message=self._require(state, "message", str),
                intent=state.get("intent", "general"),
                tool_name=state.get("tool_name", "general_tool"),
                success=state.get("success", False),
                result=result,
                error=state.get("error"),
            )
        if not final_answer and state.get("tool_name"):
            final_answer = state.get("last_tool_answer", "") or self.response_formatter.build(
                message=self._require(state, "message", str),
                intent=state.get("intent", "general"),
                tool_name=state.get("tool_name", "general_tool"),
                success=state.get("success", False),
                result=result,
                error=state.get("error"),
            )
        if not final_answer:
            final_answer = state.get("last_tool_answer", "") or "未能生成回答。"
            mode = "tool_result_fallback" if state.get("last_tool_answer") else "empty_fallback"

        on_token = self._current_on_token()
        if state.get("planner_mode") == "tool_calling" and on_token is not None and final_answer:
            on_token(final_answer)

        trace = self._build_trace(
            {**state, "finalization_mode": mode, "final_answer": final_answer},
            result,
        )
        return {
            "final_answer": final_answer,
            "finalization_mode": mode,
            "result": result,
            "trace": trace,
            "success": state.get("success", True),
        }

    def _build_trace(self, state: AgentState, result: dict[str, Any]) -> dict[str, Any]:
        response = result.get("response", {})
        plans = state.get("current_batch_plans") or []
        last_plan = plans[-1] if plans else state.get("tool_plan", {})
        reasons = state.get("judge_reasons", [])
        trace: dict[str, Any] = {
            "runtime": "langgraph",
            "planner_mode": state.get("requested_planner_mode", state.get("planner_mode", self.planner_mode)),
            "planner_fallback": state.get("planner_fallback"),
            "judge_outcome": reasons[-1] if reasons else "complete",
            "max_steps_reached": state.get("max_steps_reached", False),
            "finalization_mode": state.get("finalization_mode", "direct"),
            "intent": state.get("intent", "general"),
            "tool_name": state.get("tool_name", "general_tool"),
            "action": result.get("action") or last_plan.get("action"),
            "params": last_plan.get("params", {}),
            "success": state.get("success", True),
            "error": state.get("error"),
            "answer_status": response.get("answer_status") or result.get("answer_status") or ("answered" if state.get("success", True) else "error"),
            "confidence": response.get("confidence") or result.get("confidence"),
            "evidence_count": response.get("evidence_count") or result.get("evidence_count", 0),
            "source_mode": response.get("source_mode") or result.get("source_mode"),
            "query_type": response.get("query_type") or result.get("query_type"),
            "citations": response.get("citations") or result.get("citations", []),
            "retrieved_chunks": response.get("retrieved_chunks") or result.get("retrieved_chunks", []),
            "steps": state.get("steps", []),
            "tool_observation_chars": state.get("tool_observation_chars", 0),
            "tool_observation_original_chars": state.get("tool_observation_original_chars", 0),
            "message_history_chars": state.get("message_history_chars", self._messages_chars(state.get("messages", []))),
            "message_history_compacted": state.get("message_history_compacted", False),
            "context_compaction_count": state.get("context_compaction_count", 0),
        }
        if reasons:
            trace["judge_outcomes"] = reasons
        plan_steps = state.get("plan_steps")
        if plan_steps:
            trace["plan"] = [
                {
                    "output_key": step.get("output_key", f"step_{index}"),
                    "intent": step.get("intent", ""),
                    "tool_name": step.get("tool_name", ""),
                    "action": step.get("action", ""),
                }
                for index, step in enumerate(plan_steps)
            ]
        return trace

    @staticmethod
    def _messages_chars(messages: list[dict[str, Any]]) -> int:
        return sum(len(str(message.get("content", ""))) for message in messages)

    def _compact_messages(
        self,
        messages: list[dict[str, Any]],
        state: AgentState,
    ) -> tuple[list[dict[str, Any]], bool, int]:
        """Preserve the protocol-critical current batch and fold older observations."""
        if len(messages) <= 4:
            return messages, False, state.get("context_compaction_count", 0)
        system = next((item for item in messages if item.get("role") == "system"), None)
        user = next((item for item in messages if item.get("role") == "user"), None)
        assistant_indexes = [index for index, item in enumerate(messages) if item.get("role") == "assistant"]
        if not assistant_indexes:
            return messages, False, state.get("context_compaction_count", 0)
        current_start = assistant_indexes[-1]
        current = messages[current_start:]
        older = messages[1:current_start] if user is not None else messages[:current_start]
        observation_lines: list[str] = []
        for item in older:
            if item.get("role") == "tool":
                observation_lines.append(str(item.get("content", "")))
            elif item.get("role") == "user" and str(item.get("content", "")).startswith(PREVIOUS_OBSERVATIONS_PREFIX):
                observation_lines.append(str(item["content"]))
        compacted: list[dict[str, Any]] = [item for item in (system, user) if item is not None]
        if observation_lines:
            compacted.append({"role": "user", "content": previous_observations_message(observation_lines)})
        compacted.extend(current)
        return compacted, True, state.get("context_compaction_count", 0) + 1

    def _should_judge(self, state: AgentState) -> bool:
        return (
            state.get("success") is False
            or self._result_needs_more_info(state)
            or (
                state.get("intent") == "general"
                and state.get("success") is True
                and settings.agent_judge_on_success_general
            )
        )

    def _result_needs_more_info(self, state: AgentState) -> bool:
        intent = state.get("intent")
        result = state.get("result") or {}
        if state.get("success") is not True:
            return False
        if intent == "regulation":
            response = result.get("response") or {}
            return response.get("answer_status") == "insufficient_evidence" or (
                response.get("mode") == "fallback" and not response.get("answer")
            )
        if intent == "news":
            plans = state.get("current_batch_plans") or []
            action = plans[-1].get("action") if plans else None
            if action in {"get_article", "get_insights", "get_rules_analysis"}:
                return False
            return result.get("articles") in ([], None)
        if intent == "race":
            return not any(result.get(key) for key in ("standings", "schedule", "race", "race_result", "season"))
        return False

    def _structured_step_results(self, state: AgentState) -> list[dict[str, Any]]:
        outputs = state.get("step_outputs", {})
        return [
            {
                "tool_name": step.get("tool_name"),
                "success": bool((outputs.get(step.get("output_key", f"step_{index}")) or {}).get("success")),
                "payload": (outputs.get(step.get("output_key", f"step_{index}")) or {}).get("payload", {}),
            }
            for index, step in enumerate(state.get("plan_steps", []))
        ]

    @staticmethod
    def _extract_tool_answer(payload: dict[str, Any] | None) -> str:
        if not payload:
            return ""
        response = payload.get("response")
        if isinstance(response, str):
            return response.strip()
        containers = [response, payload]
        for container in containers:
            if not isinstance(container, dict):
                continue
            for key in ("answer", "final_answer", "summary", "analysis"):
                value = container.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    def _build_tool_result(self, state: AgentState) -> ToolResult:
        return ToolResult(
            tool_name=state.get("tool_name", ""),
            success=state.get("success", False),
            payload=state.get("result", {}),
            error=state.get("error"),
        )

    def _to_step(self, plan: dict[str, Any]) -> dict[str, Any]:
        tool_name = plan.get("tool_name")
        mapped_intent = self._TOOL_TO_INTENT.get(tool_name, "general") if isinstance(tool_name, str) else "general"
        return {
            "intent": plan.get("intent") or mapped_intent,
            "tool_name": tool_name,
            "action": plan.get("action"),
            "params": plan.get("params", {}),
            "output_key": plan.get("output_key", "step_0"),
        }

    def _require(self, state: AgentState, key: str, expected_type: type[T]) -> T:
        value = state.get(key)
        if not isinstance(value, expected_type):
            raise ValueError(f"Agent state is missing required key: {key}")
        return cast(T, value)

    def _set_current_on_token(self, callback: Callable[[str], None] | None) -> None:
        self._token_holder.callback = callback

    def _current_on_token(self) -> Callable[[str], None] | None:
        return cast(Callable[[str], None] | None, getattr(self._token_holder, "callback", None))

    def _build_default_checkpointer(self) -> Any:
        try:
            from langgraph.checkpoint.memory import MemorySaver
        except ImportError:
            return None
        return MemorySaver()
