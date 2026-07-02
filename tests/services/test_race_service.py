from datetime import UTC, datetime

from app.services.race_provider import StaticRaceDataProvider
from app.services.race_service import RaceService


def test_race_service_lists_schedule() -> None:
    service = RaceService(provider=StaticRaceDataProvider())

    schedule = service.list_schedule(2026)

    assert len(schedule) == 2
    assert schedule[0].grand_prix_name == "British Grand Prix"


def test_race_service_returns_next_race_from_seed_data() -> None:
    service = RaceService(provider=StaticRaceDataProvider())

    race = service.get_next_race(2026, now=datetime(2026, 7, 2, 12, 0, tzinfo=UTC))

    assert race is not None
    assert race.round_number == 9
    assert race.grand_prix_name == "British Grand Prix"


def test_race_service_lists_driver_standings() -> None:
    service = RaceService(provider=StaticRaceDataProvider())

    standings = service.list_driver_standings(2026)

    assert len(standings) == 3
    assert standings[0].driver_name == "Lando Norris"
