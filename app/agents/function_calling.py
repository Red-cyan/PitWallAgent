from __future__ import annotations

import json
from typing import Any

from openai.types.chat import ChatCompletionMessage

from app.config.settings import settings
from app.services.llm.client import LLMClient
from app.tools.base import ToolResult

SYSTEM_PROMPT = (
    "You are a Formula 1 assistant. Answer in the user's language. "
    "Use the provided tools to fetch live race data, news, FIA regulations, or strategy "
    "analysis when the question needs structured information. You may call multiple tools "
    "in one turn when the question spans capabilities. Never invent data that a tool should "
    "provide. When a tool result is insufficient, try a different query before giving up. "
    "After gathering information, reply with a grounded answer and cite evidence where relevant."
)

ACTION_TO_TOOL: dict[str, tuple[str, str]] = {
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

_TOOL_DESCRIPTIONS = {
    "list_recent": "List the most recent Formula 1 news articles.",
    "search": "Search F1 news articles by topic, team, driver, or circuit.",
    "get_article": "Fetch a single news article by its numeric id.",
    "get_insights": "Summarize and analyze a news article by id.",
    "get_rules_analysis": "Analyze how a news article relates to FIA regulations.",
    "list_schedule": "List the current F1 race calendar.",
    "get_next_race": "Get details of the next F1 race.",
    "get_previous_race": "Get details of the previous F1 race.",
    "get_race_results": "Get the results of the latest F1 race.",
    "get_driver_standings": "Get the current F1 drivers championship standings.",
    "get_constructor_standings": "Get the current F1 constructors championship standings.",
    "ask": "Answer a question grounded in the FIA Formula 1 regulations.",
    "analyze": "Provide pit-stop or tyre strategy analysis.",
    "answer": "Answer general Formula 1 knowledge questions.",
}

_PARAM_SCHEMAS: dict[str, tuple[dict[str, Any], list[str]]] = {
    "list_recent": ({"limit": {"type": "integer", "description": "Maximum number of articles"}}, []),
    "search": ({"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
    "get_article": ({"article_id": {"type": "integer"}}, ["article_id"]),
    "get_insights": ({"article_id": {"type": "integer"}}, ["article_id"]),
    "get_rules_analysis": ({"article_id": {"type": "integer"}}, ["article_id"]),
    "list_schedule": ({}, []),
    "get_next_race": ({}, []),
    "get_previous_race": ({}, []),
    "get_race_results": ({}, []),
    "get_driver_standings": ({}, []),
    "get_constructor_standings": ({}, []),
    "ask": ({"question": {"type": "string"}}, ["question"]),
    "analyze": ({"question": {"type": "string"}}, ["question"]),
    "answer": ({"question": {"type": "string"}}, ["question"]),
}


def build_tool_functions() -> list[dict[str, Any]]:
    """Return OpenAI-compatible schemas for all dispatcher actions."""
    functions: list[dict[str, Any]] = []
    for action, (intent, tool_name) in ACTION_TO_TOOL.items():
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


class ToolCallingModelAdapter:
    """One OpenAI-compatible tool-calling model invocation, with no orchestration loop."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    def invoke(self, messages: list[dict[str, Any]]) -> ChatCompletionMessage:
        client = self._llm_client or LLMClient()
        return client.chat_tools(
            messages=messages,
            tools=build_tool_functions(),
            temperature=0,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        )

    def summarize(self, messages: list[dict[str, Any]]) -> str:
        client = self._llm_client or LLMClient()
        summary_messages = [
            *messages,
            {
                "role": "user",
                "content": (
                    "The tool-call limit has been reached. Do not call any more tools. "
                    "Using only the tool results above, answer the original user question now. "
                    "Answer in the user's language, cite available evidence where relevant, "
                    "and state remaining uncertainty briefly. Keep the complete answer under "
                    "350 Chinese characters or 220 English words so it does not end mid-sentence."
                ),
            },
        ]
        return client.chat(
            messages=summary_messages,
            temperature=0,
            max_tokens=settings.llm_max_tokens,
            timeout=settings.llm_timeout_seconds,
        ).strip()

    @staticmethod
    def assistant_message(reply: ChatCompletionMessage) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": reply.content or "",
            "tool_calls": [call.model_dump() for call in (reply.tool_calls or [])],
        }

    @staticmethod
    def tool_call_to_plan(tool_call: Any) -> tuple[dict[str, Any], str | None]:
        action = tool_call.function.name
        parse_error: str | None = None
        try:
            params = json.loads(tool_call.function.arguments or "{}")
        except (json.JSONDecodeError, TypeError):
            params = {}
            parse_error = "Invalid JSON tool arguments."
        if not isinstance(params, dict):
            params = {}
            parse_error = "Tool arguments must be a JSON object."
        mapping = ACTION_TO_TOOL.get(action)
        if mapping is None:
            return {
                "intent": "general",
                "tool_name": "unknown",
                "action": action,
                "params": params,
                "tool_call_id": tool_call.id,
            }, f"Unknown tool: {action}"
        intent, tool_name = mapping
        return {
            "intent": intent,
            "tool_name": tool_name,
            "action": action,
            "params": params,
            "tool_call_id": tool_call.id,
        }, parse_error


def invalid_tool_result(plan: dict[str, Any], error: str) -> ToolResult:
    return ToolResult(tool_name=plan.get("tool_name", "unknown"), success=False, error=error)
