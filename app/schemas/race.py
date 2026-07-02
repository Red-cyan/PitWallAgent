from datetime import datetime

from pydantic import BaseModel, Field


class SessionInfo(BaseModel):
    """单个赛程会话。"""

    name: str = Field(..., min_length=1)
    start_time: datetime


class RaceWeekend(BaseModel):
    """比赛周末信息。"""

    season: int = Field(..., ge=1950)
    round_number: int = Field(..., ge=1)
    grand_prix_name: str = Field(..., min_length=1)
    circuit_name: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)
    start_date: datetime
    end_date: datetime
    sessions: list[SessionInfo] = Field(default_factory=list)
    source: str = Field(..., min_length=1)


class DriverStandingEntry(BaseModel):
    """车手积分榜条目。"""

    position: int = Field(..., ge=1)
    driver_name: str = Field(..., min_length=1)
    team_name: str = Field(..., min_length=1)
    points: int = Field(..., ge=0)
    source: str = Field(..., min_length=1)


class ConstructorStandingEntry(BaseModel):
    """车队积分榜条目。"""

    position: int = Field(..., ge=1)
    team_name: str = Field(..., min_length=1)
    points: int = Field(..., ge=0)
    source: str = Field(..., min_length=1)
