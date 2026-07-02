from typing import Any

from app.services.race_service import RaceService
from app.tools.base import ToolResult


class RaceTool:
    """比赛信息工具。"""

    name = "race_tool"
    description = "Retrieve Formula 1 race schedule and championship standings."

    def __init__(self, race_service: RaceService | None = None) -> None:
        self.race_service = race_service or RaceService()

    def invoke(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action")
        season = int(kwargs.get("season", 2026))

        try:
            if action == "list_schedule":
                schedule = self.race_service.list_schedule(season)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "season": season,
                        "schedule": [race.model_dump(mode="json") for race in schedule],
                    },
                )

            if action == "get_next_race":
                race = self.race_service.get_next_race(season)
                return ToolResult(
                    tool_name=self.name,
                    success=race is not None,
                    payload={
                        "action": action,
                        "season": season,
                        "race": race.model_dump(mode="json") if race else None,
                    },
                    error=None if race is not None else "No upcoming race found.",
                )

            if action == "get_driver_standings":
                standings = self.race_service.list_driver_standings(season)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "season": season,
                        "standings": [item.model_dump(mode="json") for item in standings],
                    },
                )

            if action == "get_constructor_standings":
                standings = self.race_service.list_constructor_standings(season)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "season": season,
                        "standings": [item.model_dump(mode="json") for item in standings],
                    },
                )

            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unsupported race tool action: {action}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
            )
