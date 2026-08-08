from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from openai.types.chat import ChatCompletionMessage

from app.agents.tool_dispatcher import ToolDispatcher
from app.config.settings import settings
from app.core.logging import log_structured
from app.schemas.agent import AgentQueryResponse
from app.services.llm.client import LLMClient

SYSTEM_PROMPT = (
    "You are a Formula 1 assistant. Answer in the user's language. "
    "Use the provided tools to fetch live race data, news, FIA regulations, or strategy "
    "analysis when the question needs structured information. You may call multiple tools "
    "in one turn when the question spans capabilities (e.g. search news first, then check "
    "the regulations mentioned). Never invent data that a tool should provide. "
    "When the tool result is insufficient, try a different query before giving up. "
    "After gathering information, reply with a grounded answer and cite the evidence where relevant."
)

# action -> (intent, tool_name)
_ACTION_TO_TOOL: dict[str, tuple[str, str]] = {
    "list_recent": ("news", "news_tool"),
    "search": ("news", "news_tool"),
    "get_article": ("news", "news_tool"),
    "get_insights": ("news", "news_tool"),
    "get_rules_analysis": ("news", "news_tool"),
    "list_schedule": ("race", "race_tool"),
    "get_next_race": ("race", "race_tool"),
    "get_previous_race": ("race", "race_tool"),
    "get_race_results": ("race", "race_tool"),
    "get_driver_standings": ("race", "race_tool"),
    "get_constructor_standings": ("race", "race_tool"),
    "ask": ("regulation", "regulation_tool"),
    "analyze": ("strategy", "strategy_tool"),
    "answer": ("general", "general_tool"),
}

_TOOL_DESCRIPTIONS: dict[str, str] = {
    "list_recent": "List the most recent Formula 1 news articles.",
    "search": "Search F1 news articles by topic, team, driver, or circuit.",
    "get_article": "Fetch a single news article by its numeric id.",
    "get_insights": "Summarize and analyze a news article by id.",
    "get_rules_analysis": "Analyze how a news article relates to FIA regulations.",
    "list_schedule": "List the current F1 race calendar.",
    "get_next_race": "Get details of the next F1 race (location, date, sessions).",
    "get_previous_race": "Get details of the previous F1 race.",
    "get_race_results": "Get the results of the latest F1 race.",
    "get_driver_standings": "Get the current F1 drivers championship standings.",
    "get_constructor_standings": "Get the current F1 constructors championship standings.",
    "ask": "Answer a question grounded in the FIA Formula 1 regulations (RAG with citations).",
    "analyze": "Provide pit-stop or tyre strategy analysis.",
    "answer": "Answer general Formula 1 knowledge questions.",
}

_PARAM_SCHEMAS: dict[str, tuple[dict[str, Any], list[str]]] = {
    "list_recent": ({"limit": {"type": "integer", "description": "Max number of articles (default 5)"}}, []),
    "search": ({"query": {"type": "string", "description": "Search topic, team, driver, or circuit"}, "limit": {"type": "integer"}}, ["query"]),
    "get_article": ({"article_id": {"type": "integer", "description": "News article numeric id"}}, ["article_id"]),
    "get_insights": ({"article_id": {"type": "integer", "description": "News article numeric id"}}, ["article_id"]),
    "get_rules_analysis": ({"article_id": {"type": "integer", "description": "News article numeric id"}}, ["article_id"]),
    "list_schedule": ({}, []),
    "get_next_race": ({}, []),
    "get_previous_race": ({}, []),
    "get_race_results": ({}, []),
    "get_driver_standings": ({}, []),
    "get_constructor_standings": ({}, []),
    "ask": ({"question": {"type": "string", "description": "Regulation question"}}, ["question"]),
    "analyze": ({"question": {"type": "string", "description": "Strategy question"}}, ["question"]),
    "answer": ({"question": {"type": "string", "description": "General F1 question"}}, ["question"]),
}


def build_tool_functions() -> list[dict[str, Any]]:
    """把全部工具动作暴露为 OpenAI-compatible function schemas。"""
    functions: list[dict[str, Any]] = []
    for action, (intent, tool_name) in _ACTION_TO_TOOL.items():
        properties, required = _PARAM_SCHEMAS[action]
        functions.append(
            {
                "type": "function",
                "function": {
                    "name": action,
                    "description": f"[{tool_name}] {_TOOL_DESCRIPTIONS[action]} (intent: {intent})",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return functions


class FunctionCallingAgent:
    """原生 function calling 路径：LLM 自主选择/并行调用工具，观察结果后继续或作答。

    与手写 planner + judge 的 manual 路径并存，用于对比灵活性与确定性。
    """

    def __init__(
        self,
        tool_dispatcher: ToolDispatcher | None = None,
        llm_client: LLMClient | None = None,
        max_steps: int | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> None:
        self.logger = logging.getLogger("pitwall.function_calling")
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher()
        self.llm_client = llm_client
        self.max_steps = max_steps if max_steps is not None else settings.agent_react_max_steps
        self.max_parallel_tool_calls = 5
        self.on_token = on_token

    def run(self, message: str, fallback_intent: str | None = None) -> AgentQueryResponse:
        started_at = __import__("time").perf_counter()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]
        tools = build_tool_functions()
        executed: list[dict[str, Any]] = []
        final_content: str | None = None
        last_call: dict[str, Any] | None = None

        for step_count in range(1, self.max_steps + 1):
            reply = self._chat(messages, tools)
            if reply.tool_calls:
                messages.append(self._assistant_tool_message(reply))
                for tool_call in reply.tool_calls[: self.max_parallel_tool_calls]:
                    result, plan = self._execute_tool_call(tool_call)
                    executed.append(
                        {
                            "step": step_count,
                            "intent": plan["intent"],
                            "tool_name": plan["tool_name"],
                            "action": plan["action"],
                            "output_key": tool_call.id,
                            "success": result.success,
                            "error": result.error,
                        }
                    )
                    last_call = plan
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result.payload, ensure_ascii=False)[:2000],
                        }
                    )
                continue

            final_content = reply.content or ""
            if final_content:
                break
            break

        if not final_content:
            final_content = "未能生成回答。"

        tool_name = (last_call or {}).get("tool_name") or "general_tool"
        intent = (last_call or {}).get("intent") or "general"
        action = (last_call or {}).get("action")
        latency_ms = round((__import__("time").perf_counter() - started_at) * 1000, 2)
        trace: dict[str, Any] = {
            "intent": intent,
            "tool_name": tool_name,
            "action": action,
            "success": True,
            "protocol": "function_calling",
            "steps": executed,
            "latency_ms_by_stage": {"agent_total": latency_ms},
        }

        log_structured(
            self.logger,
            "function_calling_completed",
            intent=intent,
            tool_calls=len(executed),
            steps=max(1, len(executed)),
        )
        return AgentQueryResponse(
            intent=intent,
            tool_name=tool_name,
            success=True,
            final_answer=final_content,
            result={"action": action, "tool_plan": last_call or {}},
            trace=trace,
        )

    def _chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatCompletionMessage:
        llm_client = self.llm_client or LLMClient()
        return llm_client.chat_tools(
            messages=messages,
            tools=tools,
            temperature=0,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )

    def _assistant_tool_message(self, reply: ChatCompletionMessage) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": reply.content or "",
            "tool_calls": [tool_call.model_dump() for tool_call in (reply.tool_calls or [])],
        }

    def _execute_tool_call(self, tool_call: Any) -> tuple[Any, dict[str, Any]]:
        action = tool_call.function.name
        try:
            params = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError:
            params = {}
        if not isinstance(params, dict):
            params = {}
        if action not in _ACTION_TO_TOOL:
            return (
                type("Result", (), {"tool_name": "unknown", "success": False, "payload": {}, "error": f"Unknown tool: {action}"})(),
                {"intent": "general", "tool_name": "unknown", "action": action, "params": params},
            )
        intent, tool_name = _ACTION_TO_TOOL[action]
        plan = {"intent": intent, "tool_name": tool_name, "action": action, "params": params}
        if self.on_token is None:
            result = self.tool_dispatcher.execute_plan(plan)
        else:
            result = self.tool_dispatcher.execute_plan(plan, on_token=self.on_token)
        return result, plan
