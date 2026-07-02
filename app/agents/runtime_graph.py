from typing import Any, TypedDict

from app.agents.intent_router import IntentRouter
from app.agents.planner import LLMQueryPlanner
from app.agents.response_formatter import AgentResponseFormatter
from app.agents.tool_dispatcher import ToolDispatcher
from app.schemas.agent import AgentQueryResponse


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
        message = state["message"]
        fallback_intent = state.get("fallback_intent")
        tool_plan = self.planner.plan(message, fallback_intent=fallback_intent)
        return {
            "message": message,
            "fallback_intent": fallback_intent,
            "intent": tool_plan["intent"],
            "tool_plan": tool_plan,
        }

    def _plan_tool_node(self, state: AgentState) -> AgentState:
        message = state["message"]
        intent = state["intent"]
        tool_plan = state.get("tool_plan") or self.tool_dispatcher.build_plan(intent=intent, message=message)
        return {
            "message": message,
            "fallback_intent": state.get("fallback_intent"),
            "intent": intent,
            "tool_plan": tool_plan,
        }

    def _execute_tool_node(self, state: AgentState) -> AgentState:
        message = state["message"]
        intent = state["intent"]
        tool_plan = state["tool_plan"]
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
            message=state["message"],
            intent=state["intent"],
            tool_name=state["tool_name"],
            success=state["success"],
            result=formatted_result,
            error=state.get("error"),
        )
        return {
            "message": state["message"],
            "fallback_intent": state.get("fallback_intent"),
            "intent": state["intent"],
            "tool_name": state["tool_name"],
            "success": state["success"],
            "result": formatted_result,
            "error": state.get("error"),
            "final_answer": final_answer,
        }
