from datetime import UTC, datetime

from app.schemas.race import ConstructorStandingEntry, DriverStandingEntry, RaceWeekend, SessionInfo
from app.tools.race_tool import RaceTool


class StubRaceService:
    def list_schedule(self, season):
        return [
            RaceWeekend(
                season=2026,
                round_number=8,
                grand_prix_name="Austrian Grand Prix",
                circuit_name="Red Bull Ring",
                country="Austria",
                start_date=datetime(2026, 6, 26, 11, 30, tzinfo=UTC),
                end_date=datetime(2026, 6, 28, 13, 0, tzinfo=UTC),
                sessions=[SessionInfo(name="Race", start_time=datetime(2026, 6, 28, 13, 0, tzinfo=UTC))],
                source="stub",
            )
        ]

    def get_next_race(self, season):
        return self.list_schedule(season)[0]

    def get_previous_race(self, season):
        return self.list_schedule(season)[0]

    def list_driver_standings(self, season) -> list[DriverStandingEntry]:
        return [
            DriverStandingEntry(position=1, driver_name="Andrea Kimi Antonelli", team_name="Mercedes", points=171, source="stub")
        ]

    def list_constructor_standings(self, season) -> list[ConstructorStandingEntry]:
        return [
            ConstructorStandingEntry(position=1, team_name="Mercedes", points=302, source="stub")
        ]


def test_race_tool_returns_schedule() -> None:
    tool = RaceTool(race_service=StubRaceService())

    result = tool.invoke(action="list_schedule")

    assert result.success is True
    assert result.payload["schedule"][0]["grand_prix_name"] == "Austrian Grand Prix"


def test_race_tool_returns_previous_race() -> None:
    tool = RaceTool(race_service=StubRaceService())

    result = tool.invoke(action="get_previous_race")

    assert result.success is True
    assert result.payload["race"]["round_number"] == 8


def test_race_tool_returns_driver_standings() -> None:
    tool = RaceTool(race_service=StubRaceService())

    result = tool.invoke(action="get_driver_standings")

    assert result.success is True
    assert result.payload["standings"][0]["driver_name"] == "Andrea Kimi Antonelli"
