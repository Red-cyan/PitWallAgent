from datetime import UTC, datetime

from app.services.race_provider import JolpicaRaceDataProvider, StaticRaceDataProvider
from app.services.race_service import RaceService


SCHEDULE_PAYLOAD = {
    "MRData": {
        "RaceTable": {
            "Races": [
                {
                    "season": "2026",
                    "round": "8",
                    "raceName": "Austrian Grand Prix",
                    "Circuit": {
                        "circuitName": "Red Bull Ring",
                        "Location": {"country": "Austria"},
                    },
                    "date": "2026-06-28",
                    "time": "13:00:00Z",
                    "FirstPractice": {"date": "2026-06-26", "time": "11:30:00Z"},
                    "SecondPractice": {"date": "2026-06-26", "time": "15:00:00Z"},
                    "ThirdPractice": {"date": "2026-06-27", "time": "10:30:00Z"},
                    "Qualifying": {"date": "2026-06-27", "time": "14:00:00Z"},
                },
                {
                    "season": "2026",
                    "round": "9",
                    "raceName": "British Grand Prix",
                    "Circuit": {
                        "circuitName": "Silverstone Circuit",
                        "Location": {"country": "United Kingdom"},
                    },
                    "date": "2026-07-05",
                    "time": "14:00:00Z",
                    "FirstPractice": {"date": "2026-07-03", "time": "11:30:00Z"},
                    "SecondPractice": {"date": "2026-07-03", "time": "15:00:00Z"},
                    "ThirdPractice": {"date": "2026-07-04", "time": "10:30:00Z"},
                    "Qualifying": {"date": "2026-07-04", "time": "14:00:00Z"},
                },
            ]
        }
    }
}

DRIVER_STANDINGS_PAYLOAD = {
    "MRData": {
        "StandingsTable": {
            "StandingsLists": [
                {
                    "DriverStandings": [
                        {
                            "position": "1",
                            "points": "171",
                            "Driver": {"givenName": "Andrea Kimi", "familyName": "Antonelli"},
                            "Constructors": [{"name": "Mercedes"}],
                        }
                    ]
                }
            ]
        }
    }
}


def test_jolpica_provider_parses_schedule() -> None:
    provider = JolpicaRaceDataProvider(
        fetch_json=lambda path: SCHEDULE_PAYLOAD,
        fallback_provider=StaticRaceDataProvider(),
    )

    schedule = provider.list_schedule(2026)

    assert len(schedule) == 2
    assert schedule[0].grand_prix_name == "Austrian Grand Prix"
    assert schedule[1].grand_prix_name == "British Grand Prix"


def test_jolpica_provider_parses_driver_standings() -> None:
    provider = JolpicaRaceDataProvider(
        fetch_json=lambda path: DRIVER_STANDINGS_PAYLOAD,
        fallback_provider=StaticRaceDataProvider(),
    )

    standings = provider.list_driver_standings(2026)

    assert len(standings) == 1
    assert standings[0].driver_name == "Andrea Kimi Antonelli"
    assert standings[0].team_name == "Mercedes"


def test_race_service_returns_next_and_previous_race() -> None:
    provider = JolpicaRaceDataProvider(
        fetch_json=lambda path: SCHEDULE_PAYLOAD,
        fallback_provider=StaticRaceDataProvider(),
    )
    service = RaceService(provider=provider)

    next_race = service.get_next_race(2026, now=datetime(2026, 7, 2, 12, 0, tzinfo=UTC))
    previous_race = service.get_previous_race(2026, now=datetime(2026, 7, 2, 12, 0, tzinfo=UTC))

    assert next_race is not None
    assert next_race.grand_prix_name == "British Grand Prix"
    assert previous_race is not None
    assert previous_race.grand_prix_name == "Austrian Grand Prix"
