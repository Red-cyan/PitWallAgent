from datetime import UTC, datetime

from app.config.settings import settings
from app.schemas.race import ConstructorStandingEntry, DriverStandingEntry, RaceWeekend
from app.services.race_provider import JolpicaRaceDataProvider, RaceDataProvider


class RaceService:
    """比赛信息服务。"""

    def __init__(self, provider: RaceDataProvider | None = None) -> None:
        self.provider = provider or JolpicaRaceDataProvider()

    def list_schedule(self, season: int | str | None = None) -> list[RaceWeekend]:
        resolved_season = season or settings.race_default_season
        return self.provider.list_schedule(resolved_season)

    def get_next_race(self, season: int | str | None = None, now: datetime | None = None) -> RaceWeekend | None:
        current_time = now or datetime.now(UTC)
        schedule = self.list_schedule(season)

        upcoming_races = [race for race in schedule if race.end_date >= current_time]
        if not upcoming_races:
            return None

        upcoming_races.sort(key=lambda race: race.start_date)
        return upcoming_races[0]

    def get_previous_race(self, season: int | str | None = None, now: datetime | None = None) -> RaceWeekend | None:
        current_time = now or datetime.now(UTC)
        schedule = self.list_schedule(season)

        previous_races = [race for race in schedule if race.end_date < current_time]
        if not previous_races:
            return None

        previous_races.sort(key=lambda race: race.end_date, reverse=True)
        return previous_races[0]

    def list_driver_standings(self, season: int | str | None = None) -> list[DriverStandingEntry]:
        resolved_season = season or settings.race_default_season
        return self.provider.list_driver_standings(resolved_season)

    def list_constructor_standings(self, season: int | str | None = None) -> list[ConstructorStandingEntry]:
        resolved_season = season or settings.race_default_season
        return self.provider.list_constructor_standings(resolved_season)
