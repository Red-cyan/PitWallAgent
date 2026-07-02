from fastapi import APIRouter, HTTPException, Query

from app.schemas.race import ConstructorStandingEntry, DriverStandingEntry, RaceWeekend
from app.services.race_service import RaceService

router = APIRouter(prefix="/api/race", tags=["race"])
race_service = RaceService()


@router.get("/schedule", response_model=list[RaceWeekend])
def list_race_schedule(season: str | None = Query(default=None)) -> list[RaceWeekend]:
    return race_service.list_schedule(season=season)


@router.get("/next", response_model=RaceWeekend)
def get_next_race(season: str | None = Query(default=None)) -> RaceWeekend:
    race = race_service.get_next_race(season=season)
    if race is None:
        raise HTTPException(status_code=404, detail="No upcoming race found.")
    return race


@router.get("/previous", response_model=RaceWeekend)
def get_previous_race(season: str | None = Query(default=None)) -> RaceWeekend:
    race = race_service.get_previous_race(season=season)
    if race is None:
        raise HTTPException(status_code=404, detail="No previous race found.")
    return race


@router.get("/standings/drivers", response_model=list[DriverStandingEntry])
def list_driver_standings(season: str | None = Query(default=None)) -> list[DriverStandingEntry]:
    return race_service.list_driver_standings(season=season)


@router.get("/standings/constructors", response_model=list[ConstructorStandingEntry])
def list_constructor_standings(season: str | None = Query(default=None)) -> list[ConstructorStandingEntry]:
    return race_service.list_constructor_standings(season=season)
