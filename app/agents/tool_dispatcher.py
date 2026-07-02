import logging

from app.core.logging import log_structured
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

    def build_plan(self, intent: str, message: str) -> dict:
        if intent == "news":
            return {
                "tool_name": self.news_tool.name,
                "action": "list_recent",
                "params": {"limit": 5},
            }

        if intent == "race":
            lowered = message.lower()
            driver_subject_tokens = (
                "verstappen",
                "norris",
                "leclerc",
                "russell",
                "hamilton",
                "piastri",
                "\u7ef4\u65af\u5854\u6f58",
                "\u8bfa\u91cc\u65af",
                "\u52d2\u514b\u83b1\u5c14",
                "\u62c9\u585e\u5c14",
                "\u6c49\u5bc6\u5c14\u987f",
                "\u76ae\u4e9a\u65af\u7279\u91cc",
            )

            if (
                "constructor" in lowered
                or "team standings" in lowered
                or "constructors" in lowered
                or "team" in lowered
                or "\u8f66\u961f" in message
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
                or "\u8f66\u624b" in message
                or "\u79ef\u5206" in message
                or any(token in lowered or token in message for token in driver_subject_tokens)
            ):
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_driver_standings",
                    "params": {},
                }

            if "previous" in lowered or "last race" in lowered or "\u4e0a\u4e00\u7ad9" in message or "\u4e0a\u4e00\u573a" in message:
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_previous_race",
                    "params": {},
                }

            if "next" in lowered or "\u4e0b\u4e00\u7ad9" in message or "\u4e0b\u4e00\u573a" in message:
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_next_race",
                    "params": {},
                }

            if any(token in lowered or token in message for token in ("time", "date", "when", "\u65f6\u95f4", "\u65e5\u671f", "\u51e0\u70b9")):
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

    def execute_plan(self, plan: dict) -> ToolResult:
        tool_name = plan["tool_name"]
        action = plan["action"]
        params = plan.get("params", {})

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
            return result

        if tool_name == self.news_tool.name:
            result = self.news_tool.invoke(action=action, **params)
            log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
            return result

        if tool_name == self.race_tool.name:
            result = self.race_tool.invoke(action=action, **params)
            log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
            return result

        if tool_name == self.regulation_tool.name:
            result = self.regulation_tool.invoke(action=action, **params)
            log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
            return result

        if tool_name == self.strategy_tool.name:
            result = self.strategy_tool.invoke(action=action, **params)
            log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
            return result

        if tool_name == self.general_tool.name:
            result = self.general_tool.invoke(action=action, **params)
            log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
            return result

        result = ToolResult(
            tool_name="dispatcher",
            success=False,
            error=f"Unsupported tool name: {tool_name}",
        )
        log_structured(self.logger, "tool_plan_completed", tool_name=result.tool_name, action=action, success=result.success)
        return result

    def dispatch(self, intent: str, message: str) -> ToolResult:
        plan = self.build_plan(intent=intent, message=message)
        return self.execute_plan(plan)
