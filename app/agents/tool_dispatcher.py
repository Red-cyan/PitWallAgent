import logging

from app.core.logging import log_structured
from app.tools.base import ToolResult
from app.tools.news_tool import NewsTool
from app.tools.race_tool import RaceTool
from app.tools.regulation_tool import RegulationTool
from app.tools.strategy_tool import StrategyTool


class ToolDispatcher:
    """最小工具分发器。"""

    def __init__(
        self,
        news_tool: NewsTool | None = None,
        race_tool: RaceTool | None = None,
        regulation_tool: RegulationTool | None = None,
        strategy_tool: StrategyTool | None = None,
    ) -> None:
        self.logger = logging.getLogger("pitwall.dispatcher")
        self.news_tool = news_tool or NewsTool()
        self.race_tool = race_tool or RaceTool()
        self.regulation_tool = regulation_tool or RegulationTool()
        self.strategy_tool = strategy_tool or StrategyTool()

    def build_plan(self, intent: str, message: str) -> dict:
        if intent == "news":
            return {
                "tool_name": self.news_tool.name,
                "action": "list_recent",
                "params": {"limit": 5},
            }

        if intent == "race":
            lowered = message.lower()
            if "constructor" in lowered or "team standings" in lowered or "车队" in message:
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_constructor_standings",
                    "params": {},
                }
            if "driver" in lowered or "championship" in lowered or "积分榜" in message:
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_driver_standings",
                    "params": {},
                }
            if "previous" in lowered or "last race" in lowered or "上一站" in message:
                return {
                    "tool_name": self.race_tool.name,
                    "action": "get_previous_race",
                    "params": {},
                }
            if "next" in lowered or "下一站" in message:
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
            log_structured(
                self.logger,
                "tool_plan_completed",
                tool_name=result.tool_name,
                action=action,
                success=result.success,
            )
            return result

        if tool_name == self.race_tool.name:
            result = self.race_tool.invoke(action=action, **params)
            log_structured(
                self.logger,
                "tool_plan_completed",
                tool_name=result.tool_name,
                action=action,
                success=result.success,
            )
            return result

        if tool_name == self.regulation_tool.name:
            result = self.regulation_tool.invoke(action=action, **params)
            log_structured(
                self.logger,
                "tool_plan_completed",
                tool_name=result.tool_name,
                action=action,
                success=result.success,
            )
            return result

        if tool_name == self.strategy_tool.name:
            result = self.strategy_tool.invoke(action=action, **params)
            log_structured(
                self.logger,
                "tool_plan_completed",
                tool_name=result.tool_name,
                action=action,
                success=result.success,
            )
            return result

        result = ToolResult(
            tool_name="dispatcher",
            success=False,
            error=f"Unsupported tool name: {tool_name}",
        )
        log_structured(
            self.logger,
            "tool_plan_completed",
            tool_name=result.tool_name,
            action=action,
            success=result.success,
        )
        return result

    def dispatch(self, intent: str, message: str) -> ToolResult:
        plan = self.build_plan(intent=intent, message=message)
        return self.execute_plan(plan)
