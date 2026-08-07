from app.services.data_cache import DataCache


class DictCacheClient:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value


def test_data_cache_get_returns_none_when_disabled() -> None:
    cache = DataCache(client=DictCacheClient(), enabled=False)

    assert cache.get_last_good("k") is None


def test_data_cache_set_then_get_round_trip() -> None:
    cache = DataCache(client=DictCacheClient())

    cache.set_last_good("driver_standings:2026", [{"position": 1}], "2026-08-06T12:00:00+00:00")

    payload = cache.get_last_good("driver_standings:2026")
    assert payload is not None
    assert payload["fetched_at"] == "2026-08-06T12:00:00+00:00"
    assert payload["data"] == [{"position": 1}]


def test_data_cache_get_missing_key_returns_none() -> None:
    cache = DataCache(client=DictCacheClient())

    assert cache.get_last_good("missing") is None


def test_data_cache_get_returns_none_for_corrupt_value() -> None:
    client = DictCacheClient()
    client.data["last_good:broken"] = "not-json"
    cache = DataCache(client=client)

    assert cache.get_last_good("broken") is None
