from datetime import UTC, datetime
from typing import Any, Callable, Protocol

import httpx

from app.config.settings import settings
from app.schemas.race import ConstructorStandingEntry, DriverStandingEntry, RaceWeekend, SessionInfo


class RaceDataProvider(Protocol):
    """比赛数据提供者接口。"""

    def list_schedule(self, season: int | str) -> list[RaceWeekend]:
        """获取指定赛季赛历。"""

    def list_driver_standings(self, season: int | str) -> list[DriverStandingEntry]:
        """获取车手积分榜。"""

    def list_constructor_standings(self, season: int | str) -> list[ConstructorStandingEntry]:
        """获取车队积分榜。"""


class StaticRaceDataProvider:
    """本地种子比赛数据提供者。"""

    SOURCE = "local_seed"

    def list_schedule(self, season: int | str) -> list[RaceWeekend]:
        if str(season) not in {"2026", "current"}:
            return []

        return [
            RaceWeekend(
                season=2026,
                round_number=9,
                grand_prix_name="British Grand Prix",
                circuit_name="Silverstone Circuit",
                country="United Kingdom",
                start_date=datetime(2026, 7, 3, 11, 30, tzinfo=UTC),
                end_date=datetime(2026, 7, 5, 14, 0, tzinfo=UTC),
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
                start_date=datetime(2026, 7, 17, 11, 30, tzinfo=UTC),
                end_date=datetime(2026, 7, 19, 14, 0, tzinfo=UTC),
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

    def list_driver_standings(self, season: int | str) -> list[DriverStandingEntry]:
        if str(season) not in {"2026", "current"}:
            return []

        return [
            DriverStandingEntry(position=1, driver_name="Andrea Kimi Antonelli", team_name="Mercedes", points=171, source=self.SOURCE),
            DriverStandingEntry(position=2, driver_name="George Russell", team_name="Mercedes", points=131, source=self.SOURCE),
            DriverStandingEntry(position=3, driver_name="Charles Leclerc", team_name="Ferrari", points=112, source=self.SOURCE),
        ]

    def list_constructor_standings(self, season: int | str) -> list[ConstructorStandingEntry]:
        if str(season) not in {"2026", "current"}:
            return []

        return [
            ConstructorStandingEntry(position=1, team_name="Mercedes", points=302, source=self.SOURCE),
            ConstructorStandingEntry(position=2, team_name="Ferrari", points=204, source=self.SOURCE),
            ConstructorStandingEntry(position=3, team_name="McLaren", points=159, source=self.SOURCE),
        ]


class JolpicaRaceDataProvider:
    """基于 Jolpica / Ergast 兼容接口的比赛数据提供者。"""

    SOURCE = "jolpica_api"
    SESSION_KEYS = (
        ("FirstPractice", "Practice 1"),
        ("SecondPractice", "Practice 2"),
        ("ThirdPractice", "Practice 3"),
        ("SprintQualifying", "Sprint Qualifying"),
        ("Sprint", "Sprint"),
        ("Qualifying", "Qualifying"),
    )

    def __init__(
        self,
        base_url: str | None = None,
        fetch_json: Callable[[str], dict] | None = None,
        fallback_provider: RaceDataProvider | None = None,
    ) -> None:
        self.base_url = (base_url or settings.race_data_base_url).rstrip("/")
        self.fetch_json = fetch_json or self._fetch_json
        self.fallback_provider = fallback_provider or StaticRaceDataProvider()

    def list_schedule(self, season: int | str) -> list[RaceWeekend]:
        try:
            payload = self.fetch_json(f"{season}.json")
            races = payload["MRData"]["RaceTable"]["Races"]
            return [self._parse_race_weekend(item) for item in races]
        except Exception:
            return self.fallback_provider.list_schedule(season)

    def list_driver_standings(self, season: int | str) -> list[DriverStandingEntry]:
        try:
            payload = self.fetch_json(f"{season}/driverstandings.json")
            standings = payload["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
            return [self._parse_driver_standing(item) for item in standings]
        except Exception:
            return self.fallback_provider.list_driver_standings(season)

    def list_constructor_standings(self, season: int | str) -> list[ConstructorStandingEntry]:
        try:
            payload = self.fetch_json(f"{season}/constructorstandings.json")
            standings = payload["MRData"]["StandingsTable"]["StandingsLists"][0]["ConstructorStandings"]
            return [self._parse_constructor_standing(item) for item in standings]
        except Exception:
            return self.fallback_provider.list_constructor_standings(season)

    def _fetch_json(self, path: str) -> dict:
        response = httpx.get(
            f"{self.base_url}/{path}",
            timeout=settings.race_request_timeout_seconds,
            headers={"User-Agent": settings.news_user_agent},
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.json()

    def _parse_race_weekend(self, item: dict[str, Any]) -> RaceWeekend:
        race_session = SessionInfo(
            name="Race",
            start_time=self._parse_datetime(item["date"], item.get("time")),
        )
        sessions: list[SessionInfo] = []

        for key, label in self.SESSION_KEYS:
            session_payload = item.get(key)
            if not isinstance(session_payload, dict):
                continue
            sessions.append(
                SessionInfo(
                    name=label,
                    start_time=self._parse_datetime(session_payload["date"], session_payload.get("time")),
                )
            )

        sessions.append(race_session)
        sessions.sort(key=lambda session: session.start_time)

        return RaceWeekend(
            season=int(item["season"]),
            round_number=int(item["round"]),
            grand_prix_name=item["raceName"],
            circuit_name=item["Circuit"]["circuitName"],
            country=item["Circuit"]["Location"]["country"],
            start_date=sessions[0].start_time,
            end_date=race_session.start_time,
            sessions=sessions,
            source=self.SOURCE,
        )

    def _parse_driver_standing(self, item: dict[str, Any]) -> DriverStandingEntry:
        driver = item["Driver"]
        constructors = item.get("Constructors", [])
        constructor_name = constructors[0]["name"] if constructors else "Unknown"

        return DriverStandingEntry(
            position=int(item["position"]),
            driver_name=f"{driver['givenName']} {driver['familyName']}",
            team_name=constructor_name,
            points=int(float(item["points"])),
            source=self.SOURCE,
        )

    def _parse_constructor_standing(self, item: dict[str, Any]) -> ConstructorStandingEntry:
        constructor = item["Constructor"]
        return ConstructorStandingEntry(
            position=int(item["position"]),
            team_name=constructor["name"],
            points=int(float(item["points"])),
            source=self.SOURCE,
        )

    def _parse_datetime(self, date_value: str, time_value: str | None) -> datetime:
        time_part = time_value or "00:00:00Z"
        normalized = f"{date_value}T{time_part.replace('Z', '+00:00')}"
        return datetime.fromisoformat(normalized).astimezone(UTC)
