from __future__ import annotations

from app.services.data_cache import DataCache
from app.services.race_provider import JolpicaRaceDataProvider


class DictCacheClient:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value


def _standings_payload(driver_name: str = "Max Verstappen") -> dict:
    given, family = driver_name.split(" ", 1)
    return {
        "MRData": {
            "StandingsTable": {
                "StandingsLists": [
                    {
                        "DriverStandings": [
                            {
                                "position": "1",
                                "points": "100",
                                "Driver": {"givenName": given, "familyName": family},
                                "Constructors": [{"name": "Red Bull"}],
                            }
                        ]
                    }
                ]
            }
        }
    }


def _raise_connection_error(*_args, **_kwargs):
    raise ConnectionError("upstream down")


def test_live_success_writes_last_good_cache() -> None:
    cache = DataCache(client=DictCacheClient())
    provider = JolpicaRaceDataProvider(
        fetch_json=lambda path: _standings_payload(),
        data_cache=cache,
    )

    result = provider.list_driver_standings("2026")

    assert result[0].driver_name == "Max Verstappen"
    assert result[0].source == "jolpica_api"
    assert result[0].fetched_at is not None
    assert cache.get_last_good("driver_standings:2026") is not None


def test_failure_falls_back_to_cached_data_with_source_and_timestamp() -> None:
    cache = DataCache(client=DictCacheClient())
    cache.set_last_good(
        "driver_standings:2026",
        [{"position": 1, "driver_name": "Max Verstappen", "team_name": "Red Bull", "points": 100, "source": "jolpica_api", "fetched_at": None}],
        "2026-08-06T12:00:00+00:00",
    )
    provider = JolpicaRaceDataProvider(
        fetch_json=_raise_connection_error,
        data_cache=cache,
    )

    result = provider.list_driver_standings("2026")

    assert result[0].driver_name == "Max Verstappen"
    assert result[0].source == "jolpica_cached"
    assert result[0].fetched_at == "2026-08-06T12:00:00+00:00"


def test_failure_without_cache_falls_back_to_static_seed() -> None:
    cache = DataCache(client=DictCacheClient())
    provider = JolpicaRaceDataProvider(
        fetch_json=_raise_connection_error,
        data_cache=cache,
    )

    result = provider.list_driver_standings("2026")

    assert result[0].source == "local_seed"
    assert result[0].fetched_at is None
    assert result[0].driver_name == "Andrea Kimi Antonelli"
