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
        "news": {"list_recent", "search", "get_article", "get_insights", "get_rules_analysis"},
        "race": {
            "list_schedule",
            "get_next_race",
            "get_previous_race",
            "get_race_results",
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
        heuristic_plan = self._with_steps(heuristic_plan)

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
                max_tokens=self._planner_max_tokens(message),
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
            # 非 general 的复合问题（如新闻 + 规则/策略/赛况）也可能需要多步分解
            return self._has_multi_intent_signal(message)

        normalized = message.lower().strip()
        if self._is_casual_general_message(normalized):
            return False

        looks_like_follow_up = getattr(self.intent_router, "looks_like_follow_up", None)
        if callable(looks_like_follow_up) and looks_like_follow_up(normalized):
            return False

        return True

    def _planner_max_tokens(self, message: str) -> int:
        if self._has_multi_intent_signal(message):
            return settings.llm_planner_multi_max_tokens
        return settings.llm_planner_max_tokens

    def _has_multi_intent_signal(self, message: str) -> bool:
        """检测跨能力域的复合问题（如新闻 + 规则），这类问题适合多步分解。"""
        lowered = message.lower()
        news_hit = any(
            token in lowered or token in message
            for token in ("news", "headline", "新闻", "资讯", "围场")
        )
        regulation_hit = any(
            token in lowered or token in message
            for token in ("rule", "rules", "regulation", "规则", "条例", "违规")
        )
        strategy_hit = any(
            token in lowered or token in message
            for token in ("strategy", "pit stop", "策略", "进站")
        )
        race_hit = any(
            token in lowered or token in message
            for token in ("积分", "积分榜", "车手", "车队", "standings", "下一站", "next race")
        )
        return news_hit and (regulation_hit or strategy_hit or race_hit)

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
                    "Choose the right intent and action(s) to answer the question. "
                    "Return only JSON with either {intent, action, params} for a "
                    "single step, or {steps: [{intent, action, params, output_key}]} "
                    "with 2-4 ordered dependent steps when the question spans "
                    "capabilities (e.g. find news first, then analyze it against "
                    "regulations). Each step needs a unique output_key; later steps "
                    "may reference a previous step's output with "
                    "\"$ref:<output_key>.<field_path>\" in params. "
                    "Supported intents and actions: "
                    "news:list_recent|search|get_article|get_insights|get_rules_analysis; "
                    "race:list_schedule|get_next_race|get_previous_race|get_race_results|get_driver_standings|get_constructor_standings; "
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
                    "Use news:search to find articles about a specific topic, team, driver, or circuit. "
                    "Use news:get_article for a specific article by id, get_insights for article analysis, "
                    "and get_rules_analysis when the user asks how a news article relates to FIA rules. "
                    "Prefer a multi-step plan when the answer needs two capabilities, "
                    "for example: news:search first to locate an article, then "
                    "regulation:ask to check the rules mentioned in it."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Fallback intent from previous turn: {fallback_text}\n"
                    f"User message:\n{message}\n\n"
                    "If returning a single step, use {intent, action, params}. "
                    "If returning steps, give each step a unique output_key and keep "
                    "the steps in execution order; later steps may reference earlier "
                    "outputs via \"$ref:<output_key>.<field_path>\" in params. "
                    "If regulation/strategy/general is selected, include params.question with the user message. "
                    "If news:list_recent is selected, params should include limit=5. "
                    "If a news article action is selected, params must include article_id as an integer. "
                    "Otherwise params can be empty."
                ),
            },
        ]

    def _parse_and_normalize(self, raw_response: str, message: str) -> dict[str, Any]:
        data = self._extract_json_object(raw_response)
        raw_steps = data.get("steps")
        if isinstance(raw_steps, list) and raw_steps:
            steps: list[dict[str, Any]] = []
            used_keys: set[str] = set()
            for index, raw_step in enumerate(raw_steps):
                if not isinstance(raw_step, dict):
                    raise ValueError("Invalid plan step.")
                intent = raw_step.get("intent")
                action = raw_step.get("action")
                params = raw_step.get("params")
                if not isinstance(intent, str) or intent not in self._SUPPORTED_ACTIONS:
                    raise ValueError("Unsupported planner intent in step.")
                if not isinstance(action, str) or action not in self._SUPPORTED_ACTIONS[intent]:
                    raise ValueError("Unsupported planner action in step.")
                if not isinstance(params, dict):
                    params = {}
                params = self._normalize_step_params(intent, action, params, message)
                output_key = raw_step.get("output_key")
                if not isinstance(output_key, str) or not output_key or output_key in used_keys:
                    output_key = f"step_{index}"
                used_keys.add(output_key)
                steps.append(
                    {
                        "intent": intent,
                        "tool_name": self._TOOL_NAMES[intent],
                        "action": action,
                        "params": params,
                        "output_key": output_key,
                    }
                )
            first = steps[0]
            return {
                "intent": first["intent"],
                "tool_name": first["tool_name"],
                "action": first["action"],
                "params": first["params"],
                "steps": steps,
            }

        # 单步（向后兼容）
        intent = data.get("intent")
        action = data.get("action")
        params = data.get("params", {})

        if not isinstance(intent, str) or intent not in self._SUPPORTED_ACTIONS:
            raise ValueError("Unsupported planner intent.")
        if not isinstance(action, str) or action not in self._SUPPORTED_ACTIONS[intent]:
            raise ValueError("Unsupported planner action.")
        if not isinstance(params, dict):
            params = {}

        plan: dict[str, Any] = {
            "intent": intent,
            "tool_name": self._TOOL_NAMES[intent],
            "action": action,
            "params": self._normalize_step_params(intent, action, params, message),
        }
        return self._with_steps(plan)

    def _normalize_step_params(self, intent: str, action: str, params: dict[str, Any], message: str) -> dict[str, Any]:
        """规范化单步参数：注入 question、补默认值、校验 news article_id。"""
        normalized = dict(params)
        if intent in {"regulation", "strategy", "general"}:
            normalized.setdefault("question", message)
        elif intent == "news":
            if action == "list_recent":
                normalized.setdefault("limit", 5)
            elif action in {"get_article", "get_insights", "get_rules_analysis"}:
                article_id = normalized.get("article_id")
                if isinstance(article_id, str) and article_id.startswith("$ref:"):
                    # 运行时才插值的引用，规划期不校验
                    pass
                else:
                    try:
                        if article_id is None:
                            raise ValueError("News article actions require integer article_id.")
                        normalized["article_id"] = int(article_id)
                    except (TypeError, ValueError) as exc:
                        raise ValueError("News article actions require integer article_id.") from exc
        return normalized

    def _with_steps(self, plan: dict[str, Any]) -> dict[str, Any]:
        """把单步计划包装为统一的多步结构（steps 长度为 1），保持顶层字段兼容。"""
        step = {
            "intent": plan["intent"],
            "tool_name": plan["tool_name"],
            "action": plan["action"],
            "params": plan.get("params", {}),
            "output_key": plan.get("output_key", "step_0"),
        }
        return {**plan, "steps": [step]}

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
