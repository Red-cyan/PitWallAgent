from fastapi import APIRouter

from app.schemas.strategy import StrategyAnalysisRequest, StrategyAnalysisResponse
from app.services.strategy import StrategyAnalysisService

router = APIRouter(prefix="/api/strategy", tags=["strategy"])
strategy_service = StrategyAnalysisService()


@router.post("/analyze", response_model=StrategyAnalysisResponse)
def analyze_strategy(request: StrategyAnalysisRequest) -> StrategyAnalysisResponse:
    return strategy_service.analyze(request)
