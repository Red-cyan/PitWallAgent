from app.schemas.race import ConstructorStandingEntry, DriverStandingEntry, RaceWeekend, SessionInfo
from app.tools.race_tool import RaceTool


class StubRaceService:
    def list_schedule(self, season: int) -> list[RaceWeekend]:
        return [
            RaceWeekend(
                season=season,
                round_number=9,
                grand_prix_name="British Grand Prix",
                circuit_name="Silverstone Circuit",
                country="United Kingdom",
                start_date="2026-07-03T00:00:00Z",
                end_date="2026-07-05T23:59:00Z",
                sessions=[
                    SessionInfo(name="Race", start_time="2026-07-05T14:00:00Z"),
                ],
                source="stub",
            )
        ]

    def get_next_race(self, season: int):
        return self.list_schedule(season)[0]

    def list_driver_standings(self, season: int) -> list[DriverStandingEntry]:
        return [
            DriverStandingEntry(position=1, driver_name="Lando Norris", team_name="McLaren", points=198, source="stub")
        ]

    def list_constructor_standings(self, season: int) -> list[ConstructorStandingEntry]:
        return [
            ConstructorStandingEntry(position=1, team_name="McLaren", points=384, source="stub")
        ]


def test_race_tool_returns_schedule() -> None:
    tool = RaceTool(race_service=StubRaceService())

    result = tool.invoke(action="list_schedule", season=2026)

    assert result.success is True
    assert result.payload["schedule"][0]["grand_prix_name"] == "British Grand Prix"


def test_race_tool_returns_next_race() -> None:
    tool = RaceTool(race_service=StubRaceService())

    result = tool.invoke(action="get_next_race", season=2026)

    assert result.success is True
    assert result.payload["race"]["round_number"] == 9


def test_race_tool_returns_driver_standings() -> None:
    tool = RaceTool(race_service=StubRaceService())

    result = tool.invoke(action="get_driver_standings", season=2026)

    assert result.success is True
    assert result.payload["standings"][0]["driver_name"] == "Lando Norris"
