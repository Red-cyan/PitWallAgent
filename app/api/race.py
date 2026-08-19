import re

from fastapi import APIRouter, HTTPException, Query

from app.schemas.race import ConstructorStandingEntry, DriverStandingEntry, RaceWeekend
from app.services.race_service import RaceService

router = APIRouter(prefix="/api/race", tags=["race"])
race_service = RaceService()

# 赛季参数：四位数字年份或 current，避免任意字符串拼接进上游路径。
_SEASON_PATTERN = re.compile(r"^(current|\d{4})$")


def _validate_season(season: str | None) -> str | None:
    if season is None:
        return None
    if not _SEASON_PATTERN.fullmatch(season):
        raise HTTPException(
            status_code=422,
            detail="Invalid season. Use a 4-digit year or 'current'.",
        )
    return season


@router.get("/schedule", response_model=list[RaceWeekend])
def list_race_schedule(season: str | None = Query(default=None)) -> list[RaceWeekend]:
    return race_service.list_schedule(season=_validate_season(season))


@router.get("/next", response_model=RaceWeekend)
def get_next_race(season: str | None = Query(default=None)) -> RaceWeekend:
    race = race_service.get_next_race(season=_validate_season(season))
    if race is None:
        raise HTTPException(status_code=404, detail="No upcoming race found.")
    return race


@router.get("/previous", response_model=RaceWeekend)
def get_previous_race(season: str | None = Query(default=None)) -> RaceWeekend:
    race = race_service.get_previous_race(season=_validate_season(season))
    if race is None:
        raise HTTPException(status_code=404, detail="No previous race found.")
    return race


@router.get("/standings/drivers", response_model=list[DriverStandingEntry])
def list_driver_standings(season: str | None = Query(default=None)) -> list[DriverStandingEntry]:
    return race_service.list_driver_standings(season=_validate_season(season))


@router.get("/standings/constructors", response_model=list[ConstructorStandingEntry])
def list_constructor_standings(season: str | None = Query(default=None)) -> list[ConstructorStandingEntry]:
    return race_service.list_constructor_standings(season=_validate_season(season))
