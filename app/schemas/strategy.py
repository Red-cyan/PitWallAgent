from typing import Any

from pydantic import BaseModel, Field


class StrategyAnalysisRequest(BaseModel):
    """策略分析请求。"""

    question: str = Field(..., min_length=1)
    race_context: dict[str, Any] = Field(default_factory=dict)
    regulation_context: list[str] = Field(default_factory=list)
    news_context: list[str] = Field(default_factory=list)
    additional_context: str | None = None


class StrategyAnalysisResponse(BaseModel):
    """策略分析响应。"""

    question: str = Field(..., min_length=1)
    recommendation: str = Field(..., min_length=1)
    confidence: str = Field(..., min_length=1)
    facts: list[str] = Field(default_factory=list)
    analysis: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
