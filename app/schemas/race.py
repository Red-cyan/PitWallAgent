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
    fetched_at: str | None = Field(default=None, description="When the data was last fetched successfully (ISO-8601).")


class DriverStandingEntry(BaseModel):
    """车手积分榜条目。"""

    position: int = Field(..., ge=1)
    driver_name: str = Field(..., min_length=1)
    team_name: str = Field(..., min_length=1)
    points: int = Field(..., ge=0)
    source: str = Field(..., min_length=1)
    fetched_at: str | None = Field(default=None, description="When the data was last fetched successfully (ISO-8601).")


class ConstructorStandingEntry(BaseModel):
    """车队积分榜条目。"""

    position: int = Field(..., ge=1)
    team_name: str = Field(..., min_length=1)
    points: int = Field(..., ge=0)
    source: str = Field(..., min_length=1)
    fetched_at: str | None = Field(default=None, description="When the data was last fetched successfully (ISO-8601).")


class RaceResultEntry(BaseModel):
    """单场比赛结果条目。"""

    position: int = Field(..., ge=1)
    driver_name: str = Field(..., min_length=1)
    team_name: str = Field(..., min_length=1)
    points: int = Field(..., ge=0)
    grid: int | None = Field(default=None, ge=1)
    laps: int | None = Field(default=None, ge=0)
    status: str | None = Field(default=None)
    time: str | None = Field(default=None, description="Finish time as raw string.")
    source: str = Field(..., min_length=1)


class RaceResult(BaseModel):
    """单场比赛结果。"""

    season: int = Field(..., ge=1950)
    round_number: int = Field(..., ge=1)
    grand_prix_name: str = Field(..., min_length=1)
    circuit_name: str | None = None
    country: str | None = None
    results: list[RaceResultEntry] = Field(default_factory=list)
    source: str = Field(..., min_length=1)
    fetched_at: str | None = Field(default=None, description="When the data was last fetched successfully (ISO-8601).")
