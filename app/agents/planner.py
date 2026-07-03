from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agents.intent_router import IntentRouter
from app.agents.tool_dispatcher import ToolDispatcher
from app.config.settings import settings
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
        heuristic_plan = self._build_heuristic_plan(
            intent=heuristic_intent,
            message=message,
        )
        if heuristic_plan.get("tool_name") == self._TOOL_NAMES["news"]:
            heuristic_intent = "news"
        heuristic_plan["intent"] = heuristic_intent

        if not self._should_use_llm_planner(message, heuristic_intent):
            log_structured(
                self.logger,
                "query_planner_completed",
                mode="heuristic",
                intent=heuristic_plan["intent"],
                tool_name=heuristic_plan["tool_name"],
                action=heuristic_plan["action"],
            )
            return heuristic_plan

        try:
            llm_client = self.llm_client or LLMClient()
            raw_response = llm_client.chat(
                messages=self._build_messages(message, fallback_intent=fallback_intent),
                temperature=0,
                max_tokens=settings.llm_planner_max_tokens,
                timeout=settings.llm_planner_timeout_seconds,
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

    def _build_heuristic_plan(self, *, intent: str, message: str) -> dict[str, Any]:
        article_plan = self._build_news_article_plan(message)
        if article_plan is not None:
            return article_plan

        return self.tool_dispatcher.build_plan(intent=intent, message=message)

    def _build_news_article_plan(self, message: str) -> dict[str, Any] | None:
        lowered = message.lower()
        if "news" not in lowered and "article" not in lowered and "新闻" not in message and "文章" not in message:
            return None

        article_match = re.search(r"(?:article|news|新闻|文章)\s*#?\s*(\d+)", lowered)
        if article_match is None:
            return None

        article_id = int(article_match.group(1))
        if any(token in lowered or token in message for token in ("rule", "rules", "regulation", "规则", "条例", "关联")):
            action = "get_rules_analysis"
        elif any(token in lowered or token in message for token in ("insight", "analysis", "analyze", "分析", "解读")):
            action = "get_insights"
        else:
            action = "get_article"

        return {
            "tool_name": self._TOOL_NAMES["news"],
            "action": action,
            "params": {"article_id": article_id},
        }

    def _should_use_llm_planner(self, message: str, heuristic_intent: str) -> bool:
        if not settings.llm_planner_enabled and self.llm_client is None:
            return False

        if heuristic_intent != "general":
            return False

        normalized = message.lower().strip()
        if self._is_casual_general_message(normalized):
            return False

        looks_like_follow_up = getattr(self.intent_router, "looks_like_follow_up", None)
        if callable(looks_like_follow_up) and looks_like_follow_up(normalized):
            return False

        return True

    def _is_casual_general_message(self, normalized: str) -> bool:
        casual_messages = {
            "你好",
            "您好",
            "hello",
            "hi",
            "hey",
            "你是谁",
            "你能做什么",
            "你可以做什么",
        }
        if normalized in casual_messages:
            return True

        casual_tokens = (
            "谢谢",
            "thanks",
            "thank you",
            "不对",
            "不对不对",
        )
        return any(token in normalized for token in casual_tokens)

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
                    "Use regulation for FIA/F1 rules, penalties, infringements, stewards, investigations, "
                    "race control, flags, safety procedures, pit lane rules, parc ferme, technical legality, "
                    "dangerous driving, unsafe release, speeding, track limits, and questions asking whether "
                    "something is allowed or how it is punished. "
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
