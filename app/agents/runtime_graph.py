from typing import Any, TypeVar, TypedDict, cast

from app.agents.intent_router import IntentRouter
from app.agents.planner import LLMQueryPlanner
from app.agents.response_formatter import AgentResponseFormatter
from app.agents.tool_dispatcher import ToolDispatcher
from app.schemas.agent import AgentQueryResponse

T = TypeVar("T")


class AgentState(TypedDict, total=False):
    """最小 Agent 状态。"""

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


class LangGraphAgentRuntime:
    """基于 LangGraph 的最小 Agent Runtime。"""

    def __init__(
        self,
        intent_router: IntentRouter | None = None,
        planner: LLMQueryPlanner | None = None,
        tool_dispatcher: ToolDispatcher | None = None,
        response_formatter: AgentResponseFormatter | None = None,
    ) -> None:
        self.intent_router = intent_router or IntentRouter()
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher()
        self.planner = planner or LLMQueryPlanner(
            intent_router=self.intent_router,
            tool_dispatcher=self.tool_dispatcher,
        )
        self.response_formatter = response_formatter or AgentResponseFormatter()
        self.graph = self._build_graph()

    def run(self, message: str, fallback_intent: str | None = None) -> AgentQueryResponse:
        state = self.graph.invoke({"message": message, "fallback_intent": fallback_intent})
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
        graph.add_node("format_response", self._format_response_node)

        graph.add_edge(START, "classify_intent")
        graph.add_edge("classify_intent", "plan_tool")
        graph.add_edge("plan_tool", "execute_tool")
        graph.add_edge("execute_tool", "format_response")
        graph.add_edge("format_response", END)

        return graph.compile()

    def _classify_intent_node(self, state: AgentState) -> AgentState:
        message = self._require(state, "message", str)
        fallback_intent = state.get("fallback_intent")
        tool_plan = self.planner.plan(message, fallback_intent=fallback_intent)
        return {
            "message": message,
            "fallback_intent": fallback_intent,
            "intent": tool_plan["intent"],
            "tool_plan": tool_plan,
        }

    def _plan_tool_node(self, state: AgentState) -> AgentState:
        message = self._require(state, "message", str)
        intent = self._require(state, "intent", str)
        tool_plan = state.get("tool_plan") or self.tool_dispatcher.build_plan(intent=intent, message=message)
        return {
            "message": message,
            "fallback_intent": state.get("fallback_intent"),
            "intent": intent,
            "tool_plan": tool_plan,
        }

    def _execute_tool_node(self, state: AgentState) -> AgentState:
        message = self._require(state, "message", str)
        intent = self._require(state, "intent", str)
        tool_plan = self._require(state, "tool_plan", dict)
        result = self.tool_dispatcher.execute_plan(tool_plan)
        return {
            "message": message,
            "fallback_intent": state.get("fallback_intent"),
            "intent": intent,
            "tool_plan": tool_plan,
            "tool_name": result.tool_name,
            "success": result.success,
            "result": result.payload,
            "error": result.error,
        }

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
    ) -> dict[str, Any]:
        tool_plan = result.get("tool_plan", {})
        response = result.get("response", {})
        return {
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
        }
