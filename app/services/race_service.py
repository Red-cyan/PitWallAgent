from datetime import UTC, datetime

from app.schemas.race import ConstructorStandingEntry, DriverStandingEntry, RaceWeekend
from app.services.race_provider import RaceDataProvider, StaticRaceDataProvider


class RaceService:
    """比赛信息服务。"""

    def __init__(self, provider: RaceDataProvider | None = None) -> None:
        self.provider = provider or StaticRaceDataProvider()

    def list_schedule(self, season: int) -> list[RaceWeekend]:
        return self.provider.list_schedule(season)

    def get_next_race(self, season: int, now: datetime | None = None) -> RaceWeekend | None:
        current_time = now or datetime.now(UTC)
        schedule = self.provider.list_schedule(season)

        upcoming_races = [race for race in schedule if race.end_date >= current_time]
        if not upcoming_races:
            return None

        upcoming_races.sort(key=lambda race: race.start_date)
        return upcoming_races[0]

    def list_driver_standings(self, season: int) -> list[DriverStandingEntry]:
        return self.provider.list_driver_standings(season)

    def list_constructor_standings(self, season: int) -> list[ConstructorStandingEntry]:
        return self.provider.list_constructor_standings(season)
