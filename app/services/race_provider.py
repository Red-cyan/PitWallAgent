from datetime import UTC, datetime
import time
from typing import Any, Callable, Protocol

import httpx

from app.config.settings import settings
from app.schemas.race import ConstructorStandingEntry, DriverStandingEntry, RaceWeekend, SessionInfo


class RaceDataProvider(Protocol):
    """Provider interface for F1 schedule and standings data."""

    def list_schedule(self, season: int | str) -> list[RaceWeekend]:
        """Return the schedule for a season."""
        ...

    def list_driver_standings(self, season: int | str) -> list[DriverStandingEntry]:
        """Return driver standings for a season."""
        ...

    def list_constructor_standings(self, season: int | str) -> list[ConstructorStandingEntry]:
        """Return constructor standings for a season."""
        ...


class StaticRaceDataProvider:
    """Local seed provider used when the live race API is unavailable."""

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
    """Jolpica / Ergast-compatible race data provider."""

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
        fetch_json: Callable[[str], dict[str, Any]] | None = None,
        fallback_provider: RaceDataProvider | None = None,
    ) -> None:
        self.base_url = (base_url or settings.race_data_base_url).rstrip("/")
        self.fetch_json = fetch_json or self._fetch_json
        self.fallback_provider = fallback_provider or StaticRaceDataProvider()
        self._cache: dict[str, tuple[float, Any]] = {}

    def list_schedule(self, season: int | str) -> list[RaceWeekend]:
        cache_key = f"schedule:{season}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            payload = self.fetch_json(f"{season}.json")
            races = payload["MRData"]["RaceTable"]["Races"]
            schedule = [self._parse_race_weekend(item) for item in races]
        except Exception:
            schedule = self.fallback_provider.list_schedule(season)

        self._set_cached(cache_key, schedule)
        return schedule

    def list_driver_standings(self, season: int | str) -> list[DriverStandingEntry]:
        cache_key = f"driver_standings:{season}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            payload = self.fetch_json(f"{season}/driverstandings.json")
            standings = payload["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
            parsed = [self._parse_driver_standing(item) for item in standings]
        except Exception:
            parsed = self.fallback_provider.list_driver_standings(season)

        self._set_cached(cache_key, parsed)
        return parsed

    def list_constructor_standings(self, season: int | str) -> list[ConstructorStandingEntry]:
        cache_key = f"constructor_standings:{season}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            payload = self.fetch_json(f"{season}/constructorstandings.json")
            standings = payload["MRData"]["StandingsTable"]["StandingsLists"][0]["ConstructorStandings"]
            parsed = [self._parse_constructor_standing(item) for item in standings]
        except Exception:
            parsed = self.fallback_provider.list_constructor_standings(season)

        self._set_cached(cache_key, parsed)
        return parsed

    def _fetch_json(self, path: str) -> dict[str, Any]:
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

    def _get_cached(self, key: str) -> Any | None:
        cached = self._cache.get(key)
        if cached is None:
            return None

        expires_at, value = cached
        if expires_at <= time.monotonic():
            self._cache.pop(key, None)
            return None
        return value

    def _set_cached(self, key: str, value: Any) -> None:
        ttl_seconds = max(settings.race_cache_ttl_seconds, 0)
        if ttl_seconds == 0:
            return
        self._cache[key] = (time.monotonic() + ttl_seconds, value)
