from app.tools.news_tool import NewsTool
from app.tools.race_tool import RaceTool
from app.tools.regulation_tool import RegulationTool
from app.tools.base import ToolResult


class ToolDispatcher:
    """最小工具分发器。"""

    def __init__(
        self,
        news_tool: NewsTool | None = None,
        race_tool: RaceTool | None = None,
        regulation_tool: RegulationTool | None = None,
    ) -> None:
        self.news_tool = news_tool or NewsTool()
        self.race_tool = race_tool or RaceTool()
        self.regulation_tool = regulation_tool or RegulationTool()

    def dispatch(self, intent: str, message: str) -> ToolResult:
        if intent == "news":
            return self.news_tool.invoke(action="list_recent", limit=5)

        if intent == "race":
            lowered = message.lower()
            if "constructor" in lowered or "team standings" in lowered or "车队" in message:
                return self.race_tool.invoke(action="get_constructor_standings", season=2026)
            if "driver" in lowered or "championship" in lowered or "积分榜" in message:
                return self.race_tool.invoke(action="get_driver_standings", season=2026)
            if "next" in lowered or "下一站" in message:
                return self.race_tool.invoke(action="get_next_race", season=2026)
            return self.race_tool.invoke(action="list_schedule", season=2026)

        if intent == "regulation":
            return self.regulation_tool.invoke(action="ask", question=message)

        return ToolResult(
            tool_name="dispatcher",
            success=False,
            error=f"Unsupported intent: {intent}",
        )
