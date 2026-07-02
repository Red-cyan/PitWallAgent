from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.intent_router import IntentRouter
from app.agents.tool_dispatcher import ToolDispatcher
from app.core.logging import log_structured
from app.services.llm.client import LLMClient


class LLMQueryPlanner:
    """Use an LLM to choose the right capability, with heuristic fallback."""

    _SUPPORTED_ACTIONS = {
        "news": {"list_recent", "get_article", "get_insights", "get_rules_analysis"},
        "race": {
            "list_schedule",
            "get_next_race",
            "get_previous_race",
            "get_driver_standings",
            "get_constructor_standings",
        },
        "regulation": {"ask"},
        "strategy": {"analyze"},
        "general": {"answer"},
    }
    _TOOL_NAMES = {
        "news": "news_tool",
        "race": "race_tool",
        "regulation": "regulation_tool",
        "strategy": "strategy_tool",
        "general": "general_tool",
    }

    def __init__(
        self,
        intent_router: IntentRouter | None = None,
        tool_dispatcher: ToolDispatcher | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.logger = logging.getLogger("pitwall.planner")
        self.intent_router = intent_router or IntentRouter()
        self.tool_dispatcher = tool_dispatcher or ToolDispatcher()
        self.llm_client = llm_client

    def plan(self, message: str, fallback_intent: str | None = None) -> dict[str, Any]:
        heuristic_intent = self.intent_router.route(message, fallback_intent=fallback_intent)
        heuristic_plan = self.tool_dispatcher.build_plan(intent=heuristic_intent, message=message)
        heuristic_plan["intent"] = heuristic_intent

        try:
            llm_client = self.llm_client or LLMClient()
            raw_response = llm_client.chat(
                messages=self._build_messages(message, fallback_intent=fallback_intent),
                temperature=0,
            )
            llm_plan = self._parse_and_normalize(raw_response, message)
            log_structured(
                self.logger,
                "query_planner_completed",
                mode="llm",
                intent=llm_plan["intent"],
                tool_name=llm_plan["tool_name"],
                action=llm_plan["action"],
            )
            return llm_plan
        except Exception as exc:
            log_structured(
                self.logger,
                "query_planner_completed",
                mode="fallback",
                intent=heuristic_plan["intent"],
                tool_name=heuristic_plan["tool_name"],
                action=heuristic_plan["action"],
                error_type=exc.__class__.__name__,
            )
            return heuristic_plan

    def _build_messages(self, message: str, fallback_intent: str | None) -> list[dict[str, str]]:
        fallback_text = fallback_intent or "none"
        return [
            {
                "role": "system",
                "content": (
                    "You are the planning module for a Formula 1 assistant. "
                    "Choose exactly one intent and one action. "
                    "Return only JSON with keys: intent, action, params. "
                    "Supported intents and actions: "
                    "news:list_recent|get_article|get_insights|get_rules_analysis; "
                    "race:list_schedule|get_next_race|get_previous_race|get_driver_standings|get_constructor_standings; "
                    "regulation:ask; "
                    "strategy:analyze; "
                    "general:answer. "
                    "Use general for greetings, open-ended F1 questions, and anything not clearly requiring a structured data tool. "
                    "Use race for standings, schedules, next/previous race, teams, drivers, championship leaders. "
                    "Use regulation for FIA rules and flags. "
                    "Use strategy for pit stop or tactical analysis. "
                    "Use news only when the user explicitly asks for news, headlines, or recent updates. "
                    "Use news:get_article for a specific article by id, get_insights for article analysis, "
                    "and get_rules_analysis when the user asks how a news article relates to FIA rules."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Fallback intent from previous turn: {fallback_text}\n"
                    f"User message:\n{message}\n\n"
                    "If regulation/strategy/general is selected, include params.question with the user message. "
                    "If news:list_recent is selected, params should include limit=5. "
                    "If a news article action is selected, params must include article_id as an integer. "
                    "Otherwise params can be empty."
                ),
            },
        ]

    def _parse_and_normalize(self, raw_response: str, message: str) -> dict[str, Any]:
        data = self._extract_json_object(raw_response)
        intent = data.get("intent")
        action = data.get("action")
        params = data.get("params", {})

        if not isinstance(intent, str) or intent not in self._SUPPORTED_ACTIONS:
            raise ValueError("Unsupported planner intent.")
        if not isinstance(action, str) or action not in self._SUPPORTED_ACTIONS[intent]:
            raise ValueError("Unsupported planner action.")
        if not isinstance(params, dict):
            params = {}

        if intent in {"regulation", "strategy", "general"}:
            params["question"] = message
        elif intent == "news":
            if action == "list_recent":
                params.setdefault("limit", 5)
            else:
                try:
                    params["article_id"] = int(params["article_id"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError("News article actions require integer article_id.") from exc

        return {
            "intent": intent,
            "tool_name": self._TOOL_NAMES[intent],
            "action": action,
            "params": params,
        }

    def _extract_json_object(self, raw_response: str) -> dict[str, Any]:
        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError:
            start = raw_response.find("{")
            end = raw_response.rfind("}")
            if start == -1 or end == -1 or start >= end:
                raise ValueError("Planner did not return JSON.")
            data = json.loads(raw_response[start : end + 1])

        if not isinstance(data, dict):
            raise ValueError("Planner response must be a JSON object.")
        return data
