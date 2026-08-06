from __future__ import annotations

import json
import logging
from typing import Any

from app.config.settings import settings
from app.core.logging import log_structured
from app.services.llm.client import LLMClient
from app.tools.base import ToolResult


class ReActReflector:
    """ReAct 裁判：把工具执行结果回灌给 LLM，决定是终结还是重规划。

    当工具失败时给出修复计划，当 general 回答可能不足时允许发起补充工具调用，
    从而构成「执行 -> 观察 -> 再推理」的闭环。无 LLM 时永远返回 finish，
    保持确定性路径不变。
    """

    _SUPPORTED_ACTIONS = {
        "news": {"list_recent", "search", "get_article", "get_insights", "get_rules_analysis"},
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

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.logger = logging.getLogger("pitwall.reflector")
        self._llm_client = llm_client

    @property
    def enabled(self) -> bool:
        if not settings.agent_judge_enabled:
            return False
        if self._llm_client is not None:
            return True
        if not settings.llm_api_key:
            return False
        return True

    def judge(
        self,
        *,
        message: str,
        intent: str,
        tool_plan: dict[str, Any],
        tool_result: ToolResult,
        step_count: int,
        max_steps: int,
    ) -> dict[str, Any]:
        """根据工具结果决定下一步。

        返回 {finish, reason, next_plan}：
        - finish=True 且 next_plan 为 None -> 直接格式化最终回答；
        - finish=False 且 next_plan 非空  -> 用 next_plan 重新规划执行；
        - finish=True 且 next_plan 非空   -> 格式化的同时保留该计划供观察。
        """
        if not self.enabled:
            return {"finish": True, "reason": "judge_disabled", "next_plan": None}

        if step_count >= max_steps:
            return {
                "finish": True,
                "reason": "max_steps_reached",
                "next_plan": None,
            }

        try:
            llm_client = self._llm_client or LLMClient()
            raw_response = llm_client.chat(
                messages=self._build_messages(
                    message=message,
                    intent=intent,
                    tool_plan=tool_plan,
                    tool_result=tool_result,
                ),
                temperature=0,
                max_tokens=settings.agent_judge_max_tokens,
                timeout=settings.agent_judge_timeout_seconds,
            )
            judgement = self._parse_and_normalize(raw_response, message)
        except Exception as exc:
            log_structured(
                self.logger,
                "react_judge_fallback",
                reason="judge_error",
                error_type=exc.__class__.__name__,
            )
            return {"finish": True, "reason": "judge_error", "next_plan": None}

        log_structured(
            self.logger,
            "react_judge_completed",
            finish=judgement["finish"],
            reason=judgement["reason"],
            has_next_plan=judgement["next_plan"] is not None,
        )
        return judgement

    def _build_messages(
        self,
        *,
        message: str,
        intent: str,
        tool_plan: dict[str, Any],
        tool_result: ToolResult,
    ) -> list[dict[str, str]]:
        tool_output = json.dumps(tool_result.payload, ensure_ascii=False)[:2000]
        tool_error = tool_result.error or "none"
        return [
            {
                "role": "system",
                "content": (
                    "You are the reasoning module of a Formula 1 assistant that observes tool "
                    "results and decides the next step. Given the user question, the executed "
                    "tool plan and its result, decide whether the answer is complete or another "
                    "tool call is needed. Return only JSON with keys: finish (bool), reason "
                    "(short string), next_plan (object or null). "
                    "next_plan must contain tool_name, action and params, and only use these "
                    "supported intent/tool combinations: "
                    "news_tool:list_recent|get_article|get_insights|get_rules_analysis; "
                    "race_tool:list_schedule|get_next_race|get_previous_race|get_driver_standings|"
                    "get_constructor_standings; "
                    "regulation_tool:ask; strategy_tool:analyze; general_tool:answer. "
                    "When the tool failed, propose a corrected next_plan (e.g. fall back to "
                    "news_tool:list_recent when get_article failed). When the result already "
                    "answers the question, set finish=true and next_plan=null. "
                    "For news get_article that failed because the id is invalid, prefer "
                    "list_recent. Never invent tool names or actions outside the whitelist."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User question:\n{message}\n\n"
                    f"Executed intent: {intent}\n"
                    f"Executed plan: {json.dumps(tool_plan, ensure_ascii=False)}\n"
                    f"Tool success: {tool_result.success}\n"
                    f"Tool error: {tool_error}\n"
                    f"Tool output:\n{tool_output}"
                ),
            },
        ]

    def _parse_and_normalize(
        self,
        raw_response: str,
        message: str,
    ) -> dict[str, Any]:
        data = self._extract_json_object(raw_response)

        finish = data.get("finish", True)
        if not isinstance(finish, bool):
            finish = True
        reason = data.get("reason")
        if not isinstance(reason, str):
            reason = ""
        next_plan = data.get("next_plan")

        if finish:
            return {"finish": True, "reason": reason or "complete", "next_plan": None}

        normalized_plan = self._normalize_next_plan(next_plan, message)
        if normalized_plan is None:
            return {"finish": True, "reason": "invalid_next_plan", "next_plan": None}
        return {"finish": False, "reason": reason or "follow_up", "next_plan": normalized_plan}

    def _normalize_next_plan(
        self,
        raw_plan: Any,
        message: str,
    ) -> dict[str, Any] | None:
        if not isinstance(raw_plan, dict):
            return None

        tool_name = raw_plan.get("tool_name")
        action = raw_plan.get("action")
        params = raw_plan.get("params")

        intent = self._intent_from_tool_name(tool_name)
        if intent is None or not isinstance(action, str) or action not in self._SUPPORTED_ACTIONS[intent]:
            return None
        if not isinstance(params, dict):
            params = {}

        if intent in {"regulation", "strategy", "general"}:
            params["question"] = message
        elif intent == "news" and action == "list_recent":
            params.setdefault("limit", 5)
        elif intent == "news":
            try:
                params["article_id"] = int(params["article_id"])
            except (KeyError, TypeError, ValueError):
                return None

        return {
            "intent": intent,
            "tool_name": tool_name,
            "action": action,
            "params": params,
        }

    def _intent_from_tool_name(self, tool_name: Any) -> str | None:
        if not isinstance(tool_name, str):
            return None
        for intent, mapped_name in self._TOOL_NAMES.items():
            if tool_name == mapped_name:
                return intent
        return None

    def _extract_json_object(self, raw_response: str) -> dict[str, Any]:
        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError:
            start = raw_response.find("{")
            end = raw_response.rfind("}")
            if start == -1 or end == -1 or start >= end:
                raise ValueError("Reflector did not return JSON.")
            data = json.loads(raw_response[start : end + 1])

        if not isinstance(data, dict):
            raise ValueError("Reflector response must be a JSON object.")
        return data
