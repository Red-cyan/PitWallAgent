import logging
from typing import Any

from app.config.settings import settings
from app.core.logging import log_structured
from app.services.race_service import RaceService
from app.tools.base import ToolResult


class RaceTool:
    """比赛信息工具。"""

    name = "race_tool"
    description = "Retrieve Formula 1 race schedule and championship standings."

    def __init__(self, race_service: RaceService | None = None) -> None:
        self.logger = logging.getLogger("pitwall.tool.race")
        self.race_service = race_service or RaceService()

    def invoke(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action")
        season = kwargs.get("season", settings.race_default_season)
        log_structured(self.logger, "race_tool_invoked", action=action, season=season)

        try:
            if action == "list_schedule":
                schedule = self.race_service.list_schedule(season)
                result = ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "season": season,
                        "schedule": [race.model_dump(mode="json") for race in schedule],
                        "source": schedule[0].source if schedule else None,
                        "fetched_at": schedule[0].fetched_at if schedule else None,
                    },
                )
                log_structured(
                    self.logger,
                    "race_tool_completed",
                    action=action,
                    season=season,
                    success=result.success,
                    item_count=len(result.payload["schedule"]),
                )
                return result

            if action == "get_next_race":
                race = self.race_service.get_next_race(season)
                result = ToolResult(
                    tool_name=self.name,
                    success=race is not None,
                    payload={
                        "action": action,
                        "season": season,
                        "race": race.model_dump(mode="json") if race else None,
                        "source": race.source if race else None,
                        "fetched_at": race.fetched_at if race else None,
                    },
                    error=None if race is not None else "No upcoming race found.",
                )
                log_structured(self.logger, "race_tool_completed", action=action, season=season, success=result.success)
                return result

            if action == "get_previous_race":
                race = self.race_service.get_previous_race(season)
                result = ToolResult(
                    tool_name=self.name,
                    success=race is not None,
                    payload={
                        "action": action,
                        "season": season,
                        "race": race.model_dump(mode="json") if race else None,
                        "source": race.source if race else None,
                        "fetched_at": race.fetched_at if race else None,
                    },
                    error=None if race is not None else "No previous race found.",
                )
                log_structured(self.logger, "race_tool_completed", action=action, season=season, success=result.success)
                return result

            if action == "get_driver_standings":
                standings = self.race_service.list_driver_standings(season)
                result = ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "season": season,
                        "standings": [item.model_dump(mode="json") for item in standings],
                        "source": standings[0].source if standings else None,
                        "fetched_at": standings[0].fetched_at if standings else None,
                    },
                )
                log_structured(
                    self.logger,
                    "race_tool_completed",
                    action=action,
                    season=season,
                    success=result.success,
                    item_count=len(result.payload["standings"]),
                )
                return result

            if action == "get_constructor_standings":
                standings = self.race_service.list_constructor_standings(season)
                result = ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "season": season,
                        "standings": [item.model_dump(mode="json") for item in standings],
                        "source": standings[0].source if standings else None,
                        "fetched_at": standings[0].fetched_at if standings else None,
                    },
                )
                log_structured(
                    self.logger,
                    "race_tool_completed",
                    action=action,
                    season=season,
                    success=result.success,
                    item_count=len(result.payload["standings"]),
                )
                return result

            if action == "get_race_results":
                round_number = kwargs.get("round_number")
                race_result = self.race_service.get_race_results(season, round_number=round_number)
                result = ToolResult(
                    tool_name=self.name,
                    success=race_result is not None,
                    payload={
                        "action": action,
                        "season": season,
                        "race_result": race_result.model_dump(mode="json") if race_result else None,
                        "source": race_result.source if race_result else None,
                        "fetched_at": race_result.fetched_at if race_result else None,
                    },
                    error=None if race_result is not None else "No completed race results found.",
                )
                log_structured(self.logger, "race_tool_completed", action=action, season=season, success=result.success)
                return result

            result = ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unsupported race tool action: {action}",
            )
            log_structured(self.logger, "race_tool_completed", action=action, season=season, success=result.success)
            return result
        except Exception as exc:
            result = ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
            )
            log_structured(
                self.logger,
                "race_tool_completed",
                action=action,
                season=season,
                success=result.success,
                error_type=exc.__class__.__name__,
            )
            return result
