from typing import Any, TypedDict

from app.agents.intent_router import IntentRouter
from app.agents.tool_dispatcher import ToolDispatcher
from app.schemas.agent import AgentQueryResponse


class AgentState(TypedDict, total=False):
    """最小 Agent 状态。"""

    message: str
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
        tool_dispatcher: ToolDispatcher | None = None,
    ) -> None:
        self.intent_router = intent_router or IntentRouter()
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher()
        self.graph = self._build_graph()

    def run(self, message: str) -> AgentQueryResponse:
        state = self.graph.invoke({"message": message})
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
        intent = self.intent_router.route(message)
        return {"message": message, "intent": intent}

    def _plan_tool_node(self, state: AgentState) -> AgentState:
        message = state["message"]
        intent = state["intent"]
        tool_plan = self.tool_dispatcher.build_plan(intent=intent, message=message)
        return {
            "message": message,
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
        final_answer = self._build_final_answer(
            intent=state["intent"],
            tool_name=state["tool_name"],
            success=state["success"],
            result=formatted_result,
            error=state.get("error"),
        )
        return {
            "message": state["message"],
            "intent": state["intent"],
            "tool_name": state["tool_name"],
            "success": state["success"],
            "result": formatted_result,
            "error": state.get("error"),
            "final_answer": final_answer,
        }

    def _build_final_answer(
        self,
        intent: str,
        tool_name: str,
        success: bool,
        result: dict[str, Any],
        error: str | None,
    ) -> str:
        if not success:
            return error or f"{tool_name} 执行失败。"

        if intent == "news":
            articles = result.get("articles", [])
            if articles:
                titles = [article["title"] for article in articles[:3] if "title" in article]
                if titles:
                    return f"已获取最近的 F1 新闻，重点包括：{'；'.join(titles)}。"
            return "已完成新闻查询。"

        if intent == "race":
            race = result.get("race")
            if race and race.get("grand_prix_name"):
                return f"下一站比赛是 {race['grand_prix_name']}。"

            standings = result.get("standings", [])
            if standings:
                leader = standings[0]
                if "driver_name" in leader:
                    return f"当前车手积分榜领先者是 {leader['driver_name']}，积分 {leader['points']}。"
                if "team_name" in leader:
                    return f"当前车队积分榜领先者是 {leader['team_name']}，积分 {leader['points']}。"

            schedule = result.get("schedule", [])
            if schedule:
                next_round = schedule[0]
                return f"已获取赛历，最近一站是 {next_round['grand_prix_name']}。"

            return "已完成比赛信息查询。"

        if intent == "regulation":
            response = result.get("response", {})
            answer = response.get("answer")
            if answer:
                return answer
            return "已完成规则查询。"

        return "已完成请求处理。"
