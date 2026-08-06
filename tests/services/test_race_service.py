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

RESULTS_PAYLOAD = {
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
                    "Results": [
                        {
                            "position": "1",
                            "points": "25",
                            "grid": "1",
                            "laps": "71",
                            "status": "Finished",
                            "Time": {"time": "1:25:00.123"},
                            "Driver": {"givenName": "Andrea Kimi", "familyName": "Antonelli"},
                            "Constructor": {"name": "Mercedes"},
                        },
                        {
                            "position": "2",
                            "points": "18",
                            "grid": "3",
                            "laps": "71",
                            "status": "Finished",
                            "Time": {"time": "+8.554"},
                            "Driver": {"givenName": "Charles", "familyName": "Leclerc"},
                            "Constructor": {"name": "Ferrari"},
                        },
                    ],
                }
            ]
        }
    }
}


def test_jolpica_provider_parses_race_results() -> None:
    provider = JolpicaRaceDataProvider(
        fetch_json=lambda path: RESULTS_PAYLOAD,
        fallback_provider=StaticRaceDataProvider(),
    )

    result = provider.get_race_results(2026, round_number=8)

    assert result.grand_prix_name == "Austrian Grand Prix"
    assert len(result.results) == 2
    assert result.results[0].driver_name == "Andrea Kimi Antonelli"
    assert result.results[0].team_name == "Mercedes"
    assert result.results[0].points == 25
    assert result.results[0].grid == 1
    assert result.results[0].status == "Finished"


def test_race_service_resolves_previous_round_results() -> None:
    provider = JolpicaRaceDataProvider(
        fetch_json=lambda path: SCHEDULE_PAYLOAD if "results" not in path else RESULTS_PAYLOAD,
        fallback_provider=StaticRaceDataProvider(),
    )
    service = RaceService(provider=provider)

    result = service.get_race_results(2026, now=datetime(2026, 7, 2, 12, 0, tzinfo=UTC))

    assert result is not None
    assert result.round_number == 8
    assert result.grand_prix_name == "Austrian Grand Prix"


def test_race_service_returns_none_when_no_completed_race() -> None:
    provider = JolpicaRaceDataProvider(
        fetch_json=lambda path: SCHEDULE_PAYLOAD,
        fallback_provider=StaticRaceDataProvider(),
    )
    service = RaceService(provider=provider)

    result = service.get_race_results(2026, now=datetime(2026, 1, 1, tzinfo=UTC))

    assert result is None
