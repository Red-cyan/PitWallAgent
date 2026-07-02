from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.race import ConstructorStandingEntry, DriverStandingEntry, RaceWeekend, SessionInfo


class StubRaceService:
    def list_schedule(self, season: str | None = None) -> list[RaceWeekend]:
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
                    SessionInfo(name="Race", start_time=datetime(2026, 7, 5, 14, 0, tzinfo=UTC)),
                ],
                source="stub",
            )
        ]

    def get_next_race(self, season: str | None = None) -> RaceWeekend | None:
        return self.list_schedule(season)[0]

    def get_previous_race(self, season: str | None = None) -> RaceWeekend | None:
        return RaceWeekend(
            season=2026,
            round_number=8,
            grand_prix_name="Austrian Grand Prix",
            circuit_name="Red Bull Ring",
            country="Austria",
            start_date=datetime(2026, 6, 26, 11, 30, tzinfo=UTC),
            end_date=datetime(2026, 6, 28, 14, 0, tzinfo=UTC),
            sessions=[
                SessionInfo(name="Practice 1", start_time=datetime(2026, 6, 26, 11, 30, tzinfo=UTC)),
                SessionInfo(name="Race", start_time=datetime(2026, 6, 28, 14, 0, tzinfo=UTC)),
            ],
            source="stub",
        )

    def list_driver_standings(self, season: str | None = None) -> list[DriverStandingEntry]:
        return [
            DriverStandingEntry(position=1, driver_name="Andrea Kimi Antonelli", team_name="Mercedes", points=171, source="stub")
        ]

    def list_constructor_standings(self, season: str | None = None) -> list[ConstructorStandingEntry]:
        return [
            ConstructorStandingEntry(position=1, team_name="Mercedes", points=302, source="stub")
        ]


class EmptyRaceService(StubRaceService):
    def get_next_race(self, season: str | None = None) -> RaceWeekend | None:
        return None

    def get_previous_race(self, season: str | None = None) -> RaceWeekend | None:
        return None


def test_race_schedule_routes_request(monkeypatch) -> None:
    from app.api import race

    monkeypatch.setattr(race, "race_service", StubRaceService())
    client = TestClient(app)

    response = client.get("/api/race/schedule")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["grand_prix_name"] == "British Grand Prix"


def test_race_next_routes_request(monkeypatch) -> None:
    from app.api import race

    monkeypatch.setattr(race, "race_service", StubRaceService())
    client = TestClient(app)

    response = client.get("/api/race/next")

    assert response.status_code == 200
    assert response.json()["grand_prix_name"] == "British Grand Prix"


def test_race_previous_routes_request(monkeypatch) -> None:
    from app.api import race

    monkeypatch.setattr(race, "race_service", StubRaceService())
    client = TestClient(app)

    response = client.get("/api/race/previous")

    assert response.status_code == 200
    assert response.json()["grand_prix_name"] == "Austrian Grand Prix"


def test_driver_standings_routes_request(monkeypatch) -> None:
    from app.api import race

    monkeypatch.setattr(race, "race_service", StubRaceService())
    client = TestClient(app)

    response = client.get("/api/race/standings/drivers")

    assert response.status_code == 200
    assert response.json()[0]["driver_name"] == "Andrea Kimi Antonelli"


def test_constructor_standings_routes_request(monkeypatch) -> None:
    from app.api import race

    monkeypatch.setattr(race, "race_service", StubRaceService())
    client = TestClient(app)

    response = client.get("/api/race/standings/constructors")

    assert response.status_code == 200
    assert response.json()[0]["team_name"] == "Mercedes"


def test_race_endpoints_return_404_when_not_found(monkeypatch) -> None:
    from app.api import race

    monkeypatch.setattr(race, "race_service", EmptyRaceService())
    client = TestClient(app)

    next_response = client.get("/api/race/next")
    previous_response = client.get("/api/race/previous")

    assert next_response.status_code == 404
    assert previous_response.status_code == 404
