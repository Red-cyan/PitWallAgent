from datetime import UTC, datetime
import time
from typing import Any, Callable, Protocol

from app.config.settings import settings
from app.schemas.race import (
    ConstructorStandingEntry,
    DriverStandingEntry,
    RaceResult,
    RaceResultEntry,
    RaceWeekend,
    SessionInfo,
)
from app.services.data_cache import DataCache
from app.services.http_retry import get_with_retry


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

    def get_race_results(self, season: int | str, round_number: int) -> RaceResult:
        """Return the race results for a specific round."""
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

    def get_race_results(self, season: int | str, round_number: int) -> RaceResult:
        return RaceResult(
            season=2026,
            round_number=round_number,
            grand_prix_name="British Grand Prix",
            circuit_name="Silverstone Circuit",
            country="United Kingdom",
            results=[
                RaceResultEntry(
                    position=1,
                    driver_name="Andrea Kimi Antonelli",
                    team_name="Mercedes",
                    points=25,
                    grid=1,
                    laps=52,
                    status="Finished",
                    time="1:23:45.678",
                    source=self.SOURCE,
                ),
                RaceResultEntry(
                    position=2,
                    driver_name="George Russell",
                    team_name="Mercedes",
                    points=18,
                    grid=2,
                    laps=52,
                    status="Finished",
                    time="+5.432",
                    source=self.SOURCE,
                ),
                RaceResultEntry(
                    position=3,
                    driver_name="Charles Leclerc",
                    team_name="Ferrari",
                    points=15,
                    grid=3,
                    laps=52,
                    status="Finished",
                    time="+12.109",
                    source=self.SOURCE,
                ),
            ],
            source=self.SOURCE,
        )


class JolpicaRaceDataProvider:
    """Jolpica / Ergast-compatible race data provider."""

    SOURCE = "jolpica_api"
    CACHED_SOURCE = "jolpica_cached"
    STATIC_SOURCE = "local_seed"
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
        data_cache: DataCache | None = None,
    ) -> None:
        self.base_url = (base_url or settings.race_data_base_url).rstrip("/")
        self.fetch_json = fetch_json or self._fetch_json
        self.fallback_provider = fallback_provider or StaticRaceDataProvider()
        self.data_cache = data_cache or DataCache()
        self._cache: dict[str, tuple[float, Any]] = {}

    def list_schedule(self, season: int | str) -> list[RaceWeekend]:
        return self._load_or_fallback(
            cache_key=f"schedule:{season}",
            model_cls=RaceWeekend,
            live=lambda: self.fetch_json(f"{season}.json"),
            parse=self._parse_schedule_payload,
            static=lambda: self.fallback_provider.list_schedule(season),
        )

    def list_driver_standings(self, season: int | str) -> list[DriverStandingEntry]:
        return self._load_or_fallback(
            cache_key=f"driver_standings:{season}",
            model_cls=DriverStandingEntry,
            live=lambda: self.fetch_json(f"{season}/driverstandings.json"),
            parse=self._parse_driver_standings_payload,
            static=lambda: self.fallback_provider.list_driver_standings(season),
        )

    def list_constructor_standings(self, season: int | str) -> list[ConstructorStandingEntry]:
        return self._load_or_fallback(
            cache_key=f"constructor_standings:{season}",
            model_cls=ConstructorStandingEntry,
            live=lambda: self.fetch_json(f"{season}/constructorstandings.json"),
            parse=self._parse_constructor_standings_payload,
            static=lambda: self.fallback_provider.list_constructor_standings(season),
        )

    def get_race_results(self, season: int | str, round_number: int) -> RaceResult:
        return self._load_or_fallback(
            cache_key=f"race_results:{season}:{round_number}",
            model_cls=RaceResult,
            live=lambda: self.fetch_json(f"{season}/{round_number}/results.json"),
            parse=self._parse_results_payload,
            static=lambda: self.fallback_provider.get_race_results(season, round_number),
        )

    def _load_or_fallback(
        self,
        *,
        cache_key: str,
        model_cls: type[Any],
        live: Callable[[], dict[str, Any]],
        parse: Callable[[dict[str, Any]], Any],
        static: Callable[[], Any],
    ) -> Any:
        """Return fresh data, else the last-good Redis cache, else the static fallback.

        Live data is stored in the last-good cache so a later upstream outage
        degrades to real recent data instead of fabricated samples. The returned
        models carry ``source`` and ``fetched_at`` so callers can disclose the
        provenance to the end user.
        """
        memory = self._get_cached(cache_key)
        if memory is not None:
            return memory

        try:
            data = parse(live())
            fetched_at = datetime.now(UTC).isoformat()
            items = self._mark_source(data, self.SOURCE, fetched_at)
            self.data_cache.set_last_good(cache_key, self._to_json(data), fetched_at)
        except Exception:
            last_good = self.data_cache.get_last_good(cache_key)
            if last_good is not None:
                data = self._from_json(last_good["data"], model_cls)
                items = self._mark_source(data, self.CACHED_SOURCE, last_good.get("fetched_at"))
            else:
                data = static()
                items = self._mark_source(data, self.STATIC_SOURCE, None)

        self._set_cached(cache_key, items)
        return items

    @staticmethod
    def _mark_source(data: Any, source: str, fetched_at: str | None) -> Any:
        items = data if isinstance(data, list) else [data]
        for item in items:
            item.source = source
            item.fetched_at = fetched_at
        return data

    @staticmethod
    def _to_json(data: Any) -> list[dict[str, Any]] | dict[str, Any]:
        if isinstance(data, list):
            return [item.model_dump(mode="json") for item in data]
        return data.model_dump(mode="json")

    @staticmethod
    def _from_json(raw: Any, model_cls: type[Any]) -> Any:
        if isinstance(raw, list):
            return [model_cls.model_validate(item) for item in raw]
        return model_cls.model_validate(raw)

    def _parse_schedule_payload(self, payload: dict[str, Any]) -> list[RaceWeekend]:
        races = payload["MRData"]["RaceTable"]["Races"]
        return [self._parse_race_weekend(item) for item in races]

    def _parse_driver_standings_payload(self, payload: dict[str, Any]) -> list[DriverStandingEntry]:
        standings = payload["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
        return [self._parse_driver_standing(item) for item in standings]

    def _parse_constructor_standings_payload(self, payload: dict[str, Any]) -> list[ConstructorStandingEntry]:
        standings = payload["MRData"]["StandingsTable"]["StandingsLists"][0]["ConstructorStandings"]
        return [self._parse_constructor_standing(item) for item in standings]

    def _parse_results_payload(self, payload: dict[str, Any]) -> RaceResult:
        race_payload = payload["MRData"]["RaceTable"]["Races"][0]
        return self._parse_race_result(race_payload)

    def _parse_race_result(self, race_payload: dict[str, Any]) -> RaceResult:
        entries: list[RaceResultEntry] = []
        for item in race_payload.get("Results", []):
            driver = item["Driver"]
            constructor = item.get("Constructor") or {}
            constructors = item.get("Constructors") or []
            constructor_name = (
                constructor.get("name")
                or (constructors[0]["name"] if constructors else None)
                or "Unknown"
            )
            time_value = item.get("Time", {}).get("time") if isinstance(item.get("Time"), dict) else None
            entries.append(
                RaceResultEntry(
                    position=int(item["position"]),
                    driver_name=f"{driver['givenName']} {driver['familyName']}",
                    team_name=constructor_name,
                    points=int(float(item["points"])),
                    grid=int(item["grid"]) if item.get("grid") else None,
                    laps=int(item["laps"]) if item.get("laps") else None,
                    status=item.get("status"),
                    time=time_value,
                    source=self.SOURCE,
                )
            )

        return RaceResult(
            season=int(race_payload["season"]),
            round_number=int(race_payload["round"]),
            grand_prix_name=race_payload["raceName"],
            circuit_name=race_payload.get("Circuit", {}).get("circuitName"),
            country=race_payload.get("Circuit", {}).get("Location", {}).get("country"),
            results=entries,
            source=self.SOURCE,
        )

    def _fetch_json(self, path: str) -> dict[str, Any]:
        response = get_with_retry(
            f"{self.base_url}/{path}",
            provider="jolpica_race",
            timeout=settings.race_request_timeout_seconds,
            headers={"User-Agent": settings.news_user_agent},
            follow_redirects=True,
        )
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
