import logging
import operator
import threading
import uuid
from collections.abc import Callable
from typing import Annotated, Any, TypeVar, TypedDict, cast

from app.agents.intent_router import IntentRouter
from app.agents.planner import LLMQueryPlanner
from app.agents.reflector import ReActReflector
from app.agents.response_formatter import AgentResponseFormatter
from app.agents.tool_dispatcher import ToolDispatcher
from app.config.settings import settings
from app.schemas.agent import AgentQueryResponse

T = TypeVar("T")


class AgentState(TypedDict, total=False):
    """Agent 状态。可 JSON 序列化，on_token 不进入 state（见 run 的线程局部持有）。"""

    message: str
    fallback_intent: str | None
    intent: str
    tool_plan: dict[str, Any]
    tool_name: str
    success: bool
    result: dict[str, Any]
    error: str | None
    final_answer: str
    trace: dict[str, Any]
    judgement: dict[str, Any]
    judge_reasons: Annotated[list[str], operator.add]
    steps: Annotated[list[dict[str, Any]], operator.add]
    step_count: int
    max_steps: int


class LangGraphAgentRuntime:
    """基于 LangGraph 的 Agent Runtime，带 ReAct 循环与失败修复。

    图结构：
        START -> classify_intent -> plan_tool -> execute_tool -> judge_result
        judge_result -> route_after_judge（条件边）
            finish / 无需判断 / 超步数 -> format_response -> END
            否则（裁判给出 next_plan）  -> plan_tool（循环）
    """

    def __init__(
        self,
        intent_router: IntentRouter | None = None,
        planner: LLMQueryPlanner | None = None,
        tool_dispatcher: ToolDispatcher | None = None,
        response_formatter: AgentResponseFormatter | None = None,
        reflector: ReActReflector | None = None,
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
        self.checkpointer = checkpointer if checkpointer is not None else self._build_default_checkpointer()
        self.max_steps = max_steps if max_steps is not None else 3
        self.graph = self._build_graph()

    _token_holder = threading.local()

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
                    {"configurable": {"thread_id": uuid.uuid4().hex}},
                )
            state = self.graph.invoke(
                {
                    "message": message,
                    "fallback_intent": fallback_intent,
                    "step_count": 1,
                    "max_steps": self.max_steps,
                },
                config=config,
            )
        finally:
            self._set_current_on_token(None)

        return AgentQueryResponse(
            intent=state["intent"],
            tool_name=state["tool_name"],
            success=state["success"],
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
        graph.add_node("classify_intent", self._classify_intent_node)
        graph.add_node("plan_tool", self._plan_tool_node)
        graph.add_node("execute_tool", self._execute_tool_node)
        graph.add_node("judge_result", self._judge_result_node)
        graph.add_node("format_response", self._format_response_node)

        graph.add_edge(START, "classify_intent")
        graph.add_edge("classify_intent", "plan_tool")
        graph.add_edge("plan_tool", "execute_tool")
        graph.add_edge("execute_tool", "judge_result")
        graph.add_conditional_edges(
            "judge_result",
            self._route_after_judge,
            {
                "format_response": "format_response",
                "plan_tool": "plan_tool",
            },
        )
        graph.add_edge("format_response", END)

        return graph.compile(checkpointer=self.checkpointer)

    def _classify_intent_node(self, state: AgentState) -> AgentState:
        message = self._require(state, "message", str)
        fallback_intent = state.get("fallback_intent")
        try:
            tool_plan = self.planner.plan(message, fallback_intent=fallback_intent)
        except Exception as exc:
            log = logging.getLogger("pitwall.runtime")
            log.error("classify_intent_failed", extra={"error_type": exc.__class__.__name__})
            tool_plan = {
                "intent": "general",
                "tool_name": "general_tool",
                "action": "answer",
                "params": {"question": message},
            }
        return {
            "message": message,
            "fallback_intent": fallback_intent,
            "intent": tool_plan["intent"],
            "tool_plan": tool_plan,
            "step_count": state.get("step_count", 1),
            "max_steps": state.get("max_steps", self.max_steps),
        }

    def _plan_tool_node(self, state: AgentState) -> AgentState:
        message = self._require(state, "message", str)
        intent = self._require(state, "intent", str)
        judgement = state.get("judgement") or {}
        next_plan = judgement.get("next_plan")
        if isinstance(next_plan, dict):
            tool_plan = next_plan
        else:
            tool_plan = state.get("tool_plan") or self.tool_dispatcher.build_plan(intent=intent, message=message)
        return {
            "message": message,
            "fallback_intent": state.get("fallback_intent"),
            "intent": intent,
            "tool_plan": tool_plan,
            "step_count": state.get("step_count", 1),
            "max_steps": state.get("max_steps", self.max_steps),
        }

    def _execute_tool_node(self, state: AgentState) -> AgentState:
        message = self._require(state, "message", str)
        intent = self._require(state, "intent", str)
        tool_plan = self._require(state, "tool_plan", dict)
        on_token = self._current_on_token()
        if on_token is None:
            result = self.tool_dispatcher.execute_plan(tool_plan)
        else:
            result = self.tool_dispatcher.execute_plan(tool_plan, on_token=on_token)

        step = {
            "step": state.get("step_count", 1),
            "intent": intent,
            "tool_name": result.tool_name,
            "action": tool_plan.get("action"),
            "success": result.success,
            "error": result.error,
        }
        return {
            "message": message,
            "fallback_intent": state.get("fallback_intent"),
            "intent": intent,
            "tool_plan": tool_plan,
            "tool_name": result.tool_name,
            "success": result.success,
            "result": result.payload,
            "error": result.error,
            "step_count": state.get("step_count", 1),
            "max_steps": state.get("max_steps", self.max_steps),
            "steps": [step],
        }

    def _judge_result_node(self, state: AgentState) -> AgentState:
        step_count = state.get("step_count", 1)
        max_steps = state.get("max_steps", self.max_steps)

        if step_count >= max_steps:
            judgement = {"finish": True, "reason": "max_steps_reached", "next_plan": None}
        elif not self.reflector.enabled:
            judgement = {"finish": True, "reason": "judge_disabled", "next_plan": None}
        elif state.get("success") is False or (
            state.get("intent") == "general"
            and state.get("success") is True
            and settings.agent_judge_on_success_general
        ):
            try:
                judgement = self.reflector.judge(
                    message=self._require(state, "message", str),
                    intent=state.get("intent", "general"),
                    tool_plan=state.get("tool_plan", {}),
                    tool_result=self._build_tool_result(state),
                    step_count=step_count,
                    max_steps=max_steps,
                )
            except Exception as exc:
                log = logging.getLogger("pitwall.runtime")
                log.error("judge_result_failed", extra={"error_type": exc.__class__.__name__})
                judgement = {"finish": True, "reason": "judge_error", "next_plan": None}
        else:
            judgement = {"finish": True, "reason": "no_judge_needed", "next_plan": None}

        next_state: AgentState = {"judgement": judgement, "judge_reasons": [judgement["reason"]]}
        if judgement.get("next_plan") is not None:
            next_state["step_count"] = step_count + 1
        return next_state

    def _route_after_judge(self, state: AgentState) -> str:
        judgement = state.get("judgement") or {}
        if not judgement.get("finish", True) and judgement.get("next_plan") is not None:
            return "plan_tool"
        return "format_response"

    def _format_response_node(self, state: AgentState) -> AgentState:
        formatted_result = {
            **state.get("result", {}),
            "tool_plan": state.get("tool_plan", {}),
        }
        final_answer = self.response_formatter.build(
            message=self._require(state, "message", str),
            intent=self._require(state, "intent", str),
            tool_name=self._require(state, "tool_name", str),
            success=self._require(state, "success", bool),
            result=formatted_result,
            error=state.get("error"),
        )
        trace = self._build_trace(
            intent=self._require(state, "intent", str),
            tool_name=self._require(state, "tool_name", str),
            success=self._require(state, "success", bool),
            result=formatted_result,
            error=state.get("error"),
            judge_reasons=state.get("judge_reasons", []),
            steps=state.get("steps", []),
        )
        return {
            "message": self._require(state, "message", str),
            "fallback_intent": state.get("fallback_intent"),
            "intent": self._require(state, "intent", str),
            "tool_name": self._require(state, "tool_name", str),
            "success": self._require(state, "success", bool),
            "result": formatted_result,
            "error": state.get("error"),
            "final_answer": final_answer,
            "trace": trace,
        }

    def _require(self, state: AgentState, key: str, expected_type: type[T]) -> T:
        value = state.get(key)
        if not isinstance(value, expected_type):
            raise ValueError(f"Agent state is missing required key: {key}")
        return cast(T, value)

    def _build_trace(
        self,
        *,
        intent: str,
        tool_name: str,
        success: bool,
        result: dict[str, Any],
        error: str | None,
        judge_reasons: list[str],
        steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        tool_plan = result.get("tool_plan", {})
        response = result.get("response", {})
        trace: dict[str, Any] = {
            "intent": intent,
            "tool_name": tool_name,
            "action": result.get("action") or tool_plan.get("action"),
            "params": tool_plan.get("params", {}),
            "success": success,
            "error": error,
            "answer_status": response.get("answer_status") or result.get("answer_status") or ("answered" if success else "error"),
            "confidence": response.get("confidence") or result.get("confidence"),
            "evidence_count": response.get("evidence_count") or result.get("evidence_count", 0),
            "source_mode": response.get("source_mode") or result.get("source_mode"),
            "query_type": response.get("query_type") or result.get("query_type"),
            "citations": response.get("citations") or result.get("citations", []),
            "retrieved_chunks": response.get("retrieved_chunks") or result.get("retrieved_chunks", []),
        }
        if judge_reasons:
            trace["judge_outcomes"] = judge_reasons
            trace["judge_outcome"] = judge_reasons[-1]
        if steps:
            trace["steps"] = steps
        return trace

    def _build_tool_result(self, state: AgentState):
        from app.tools.base import ToolResult

        return ToolResult(
            tool_name=state.get("tool_name", ""),
            success=state.get("success", False),
            payload=state.get("result", {}),
            error=state.get("error"),
        )

    def _current_on_token(self) -> Callable[[str], None] | None:
        return getattr(self._token_holder, "on_token", None)

    def _set_current_on_token(self, on_token: Callable[[str], None] | None) -> None:
        self._token_holder.on_token = on_token

    def _build_default_checkpointer(self) -> Any:
        try:
            from langgraph.checkpoint.memory import MemorySaver
        except ImportError:
            return None
        return MemorySaver()
