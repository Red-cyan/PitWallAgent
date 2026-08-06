import logging
import re
import time
from collections.abc import Callable

from app.core.logging import log_structured
from app.core.metrics import TOOL_CALLS, TOOL_DURATION
from app.tools.base import ToolResult
from app.tools.general_tool import GeneralTool
from app.tools.news_tool import NewsTool
from app.tools.race_tool import RaceTool
from app.tools.regulation_tool import RegulationTool
from app.tools.strategy_tool import StrategyTool


class ToolDispatcher:
    def __init__(
        self,
        news_tool: NewsTool | None = None,
        race_tool: RaceTool | None = None,
        regulation_tool: RegulationTool | None = None,
        strategy_tool: StrategyTool | None = None,
        general_tool: GeneralTool | None = None,
    ) -> None:
        self.logger = logging.getLogger("pitwall.dispatcher")
        self.news_tool = news_tool or NewsTool()
        self.race_tool = race_tool or RaceTool()
        self.regulation_tool = regulation_tool or RegulationTool()
        self.strategy_tool = strategy_tool or StrategyTool()
        self.general_tool = general_tool or GeneralTool()

    NEWS_STOPWORDS = {
        "新闻",
        "资讯",
        "news",
        "headlines",
        "headline",
        "最近",
        "最新",
        "今天",
        "有什么",
        "看看",
        "给我",
        "讲讲",
        "关于",
        "一下",
        "的",
        "f1",
        "formula",
        "赛事",
        "有",
        "吗",
        "吧",
        "呢",
        "什么",
        "怎么",
        "哪些",
        "啥",
        "the",
        "latest",
        "recent",
        "today",
        "get",
        "give",
        "some",
        "any",
        "me",
        "about",
    }

    def build_plan(self, intent: str, message: str) -> dict:
        if intent == "news":
            return self._news_plan(message)

        if intent == "race":
            lowered = message.lower()
            driver_subject_tokens = (
                "verstappen",
                "norris",
                "leclerc",
                "russell",
                "hamilton",
                "piastri",
                "维斯塔潘",
                "诺里斯",
                "勒克莱尔",
                "拉塞尔",
                "汉密尔顿",
                "皮亚斯特里",
            )
            team_subject_tokens = (
                "red bull",
                "ferrari",
                "mclaren",
                "mercedes",
                "aston martin",
                "williams",
                "alpine",
                "haas",
                "sauber",
                "audi",
                "cadillac",
                "红牛",
                "法拉利",
                "迈凯伦",
                "梅赛德斯",
                "奔驰",
                "梅奔",
                "阿斯顿马丁",
                "威廉姆斯",
                "阿尔帕",
                "哈斯",
                "索伯",
                "奥迪",
                "凯迪拉克",
            )

            result_explicit_tokens = (
                "winner",
                "won",
                "win",
                "victory",
                "podium",
                "result",
                "results",
                "谁赢了",
                "冠军",
                "获胜",
                "胜利",
                "领奖台",
                "结果",
                "拿下",
                "制胜",
            )
            result_previous_signal = (
                "previous" in lowered
                or "last race" in lowered
                or "上一站" in message
                or "上一场" in message
            )
            result_position_signal = (
                "第几" in message
                or "名次" in message
                or "成绩" in message
                or "how did" in lowered
                or "finish" in lowered
                or "finished" in lowered
            )

            if any(token in lowered or token in message for token in result_explicit_tokens) or (
                result_previous_signal and result_position_signal
            ):
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_race_results",
                    "params": {},
                }

            if (
                "constructor" in lowered
                or "team standings" in lowered
                or "constructors" in lowered
                or "team" in lowered
                or "车队" in message
                or any(token in lowered or token in message for token in team_subject_tokens)
            ):
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_constructor_standings",
                    "params": {},
                }

            if (
                "driver" in lowered
                or "drivers" in lowered
                or "championship" in lowered
                or "车手" in message
                or "积分" in message
                or any(token in lowered or token in message for token in driver_subject_tokens)
            ):
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_driver_standings",
                    "params": {},
                }

            if "previous" in lowered or "last race" in lowered or "上一站" in message or "上一场" in message:
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_previous_race",
                    "params": {},
                }

            if "next" in lowered or "下一站" in message or "下一场" in message:
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_next_race",
                    "params": {},
                }

            if any(token in lowered or token in message for token in ("time", "date", "when", "时间", "日期", "几点")):
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_next_race",
                    "params": {},
                }

            return {
                "tool_name": self.race_tool.name,
                "action": "list_schedule",
                "params": {},
            }

        if intent == "regulation":
            return {
                "tool_name": self.regulation_tool.name,
                "action": "ask",
                "params": {"question": message},
            }

        if intent == "strategy":
            return {
                "tool_name": self.strategy_tool.name,
                "action": "analyze",
                "params": {"question": message},
            }

        if intent == "general":
            return {
                "tool_name": self.general_tool.name,
                "action": "answer",
                "params": {"question": message},
            }

        return {
            "tool_name": "dispatcher",
            "action": "unsupported",
            "params": {},
            "error": f"Unsupported intent: {intent}",
        }

    def _news_plan(self, message: str) -> dict:
        query = self._extract_news_query(message)
        if query:
            return {
                "tool_name": self.news_tool.name,
                "action": "search",
                "params": {"query": query, "limit": 5},
            }
        return {
            "tool_name": self.news_tool.name,
            "action": "list_recent",
            "params": {"limit": 5},
        }

    def _extract_news_query(self, message: str) -> str | None:
        words = sorted(self.NEWS_STOPWORDS, key=len, reverse=True)
        stop_pattern = re.compile(
            "|".join(re.escape(word) for word in words),
            re.IGNORECASE,
        )
        remaining = stop_pattern.sub(" ", message)
        remaining = re.sub(r"[\s，。,.!?！？、:：]+", " ", remaining).strip()
        tokens = [token for token in remaining.split() if token]
        if not tokens:
            return None
        query = " ".join(tokens)
        return query[:60]

    def execute_plan(
        self,
        plan: dict,
        on_token: Callable[[str], None] | None = None,
    ) -> ToolResult:
        tool_name = plan["tool_name"]
        action = plan["action"]
        params = plan.get("params", {})
        started_at = time.perf_counter()

        log_structured(
            self.logger,
            "tool_plan_executing",
            tool_name=tool_name,
            action=action,
        )

        if action == "unsupported":
            result = ToolResult(
                tool_name=tool_name,
                success=False,
                error=plan.get("error", "Unsupported plan."),
            )
            log_structured(
                self.logger,
                "tool_plan_completed",
                tool_name=result.tool_name,
                action=action,
                success=result.success,
            )
            return self._record_result(result, action, started_at)

        if tool_name == self.news_tool.name:
            result = self.news_tool.invoke(action=action, **params)
            log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
            return self._record_result(result, action, started_at)

        if tool_name == self.race_tool.name:
            result = self.race_tool.invoke(action=action, **params)
            log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
            return self._record_result(result, action, started_at)

        if tool_name == self.regulation_tool.name:
            result = self.regulation_tool.invoke(action=action, _on_token=on_token, **params)
            log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
            return self._record_result(result, action, started_at)

        if tool_name == self.strategy_tool.name:
            result = self.strategy_tool.invoke(action=action, **params)
            log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
            return self._record_result(result, action, started_at)

        if tool_name == self.general_tool.name:
            result = self.general_tool.invoke(action=action, _on_token=on_token, **params)
            log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
            return self._record_result(result, action, started_at)

        result = ToolResult(
            tool_name="dispatcher",
            success=False,
            error=f"Unsupported tool name: {tool_name}",
        )
        log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
        return self._record_result(result, action, started_at)

    def _record_result(self, result: ToolResult, action: str, started_at: float) -> ToolResult:
        outcome = "success" if result.success else "error"
        TOOL_CALLS.labels(result.tool_name, action, outcome).inc()
        TOOL_DURATION.labels(result.tool_name, action).observe(time.perf_counter() - started_at)
        return result

    def dispatch(self, intent: str, message: str) -> ToolResult:
        plan = self.build_plan(intent=intent, message=message)
        return self.execute_plan(plan)
