from datetime import UTC, datetime
from typing import Protocol

from app.schemas.race import ConstructorStandingEntry, DriverStandingEntry, RaceWeekend, SessionInfo


class RaceDataProvider(Protocol):
    """比赛数据提供者接口。"""

    def list_schedule(self, season: int) -> list[RaceWeekend]:
        """获取指定赛季赛历。"""

    def list_driver_standings(self, season: int) -> list[DriverStandingEntry]:
        """获取车手积分榜。"""

    def list_constructor_standings(self, season: int) -> list[ConstructorStandingEntry]:
        """获取车队积分榜。"""


class StaticRaceDataProvider:
    """本地种子比赛数据提供者。"""

    SOURCE = "local_seed"

    def list_schedule(self, season: int) -> list[RaceWeekend]:
        if season != 2026:
            return []

        return [
            RaceWeekend(
                season=2026,
                round_number=9,
                grand_prix_name="British Grand Prix",
                circuit_name="Silverstone Circuit",
                country="United Kingdom",
                start_date=datetime(2026, 7, 3, 0, 0, tzinfo=UTC),
                end_date=datetime(2026, 7, 5, 23, 59, tzinfo=UTC),
                sessions=[
                    SessionInfo(name="Practice 1", start_time=datetime(2026, 7, 3, 11, 30, tzinfo=UTC)),
                    SessionInfo(name="Practice 2", start_time=datetime(2026, 7, 3, 15, 0, tzinfo=UTC)),
                    SessionInfo(name="Practice 3", start_time=datetime(2026, 7, 4, 10, 30, tzinfo=UTC)),
                    SessionInfo(name="Qualifying", start_time=datetime(2026, 7, 4, 14, 0, tzinfo=UTC)),
                    SessionInfo(name="Race", start_time=datetime(2026, 7, 5, 14, 0, tzinfo=UTC)),
                ],
                source=self.SOURCE,
            ),
            RaceWeekend(
                season=2026,
                round_number=10,
                grand_prix_name="Belgian Grand Prix",
                circuit_name="Spa-Francorchamps",
                country="Belgium",
                start_date=datetime(2026, 7, 17, 0, 0, tzinfo=UTC),
                end_date=datetime(2026, 7, 19, 23, 59, tzinfo=UTC),
                sessions=[
                    SessionInfo(name="Practice 1", start_time=datetime(2026, 7, 17, 11, 30, tzinfo=UTC)),
                    SessionInfo(name="Practice 2", start_time=datetime(2026, 7, 17, 15, 0, tzinfo=UTC)),
                    SessionInfo(name="Practice 3", start_time=datetime(2026, 7, 18, 10, 30, tzinfo=UTC)),
                    SessionInfo(name="Qualifying", start_time=datetime(2026, 7, 18, 14, 0, tzinfo=UTC)),
                    SessionInfo(name="Race", start_time=datetime(2026, 7, 19, 14, 0, tzinfo=UTC)),
                ],
                source=self.SOURCE,
            ),
        ]

    def list_driver_standings(self, season: int) -> list[DriverStandingEntry]:
        if season != 2026:
            return []

        return [
            DriverStandingEntry(position=1, driver_name="Lando Norris", team_name="McLaren", points=198, source=self.SOURCE),
            DriverStandingEntry(position=2, driver_name="Oscar Piastri", team_name="McLaren", points=186, source=self.SOURCE),
            DriverStandingEntry(position=3, driver_name="Max Verstappen", team_name="Red Bull Racing", points=172, source=self.SOURCE),
        ]

    def list_constructor_standings(self, season: int) -> list[ConstructorStandingEntry]:
        if season != 2026:
            return []

        return [
            ConstructorStandingEntry(position=1, team_name="McLaren", points=384, source=self.SOURCE),
            ConstructorStandingEntry(position=2, team_name="Ferrari", points=301, source=self.SOURCE),
            ConstructorStandingEntry(position=3, team_name="Red Bull Racing", points=276, source=self.SOURCE),
        ]
