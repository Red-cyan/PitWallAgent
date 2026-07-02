from app.schemas.strategy import StrategyAnalysisRequest
from app.services.strategy import StrategyAnalysisService


class StubLLMClient:
    def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        return (
            '{"recommendation":"建议在安全车窗口内进站","confidence":"medium",'
            '"facts":["当前窗口损失较低"],'
            '"analysis":["安全车阶段可减少进站损失"],'
            '"assumptions":["当前轮胎已经进入衰减阶段"],'
            '"cautions":["若前方车流过密可能丢失位置"]}'
        )


class FailingLLMClient:
    def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        raise RuntimeError("boom")


def test_strategy_service_returns_llm_analysis() -> None:
    service = StrategyAnalysisService(llm_client=StubLLMClient())

    response = service.analyze(
        StrategyAnalysisRequest(
            question="Should Ferrari pit under safety car?",
            race_context={"tyre_age": 18, "track_position": 5},
            regulation_context=["Safety car delta applies."],
        )
    )

    assert response.recommendation == "建议在安全车窗口内进站"
    assert response.confidence == "medium"
    assert response.analysis[0] == "安全车阶段可减少进站损失"


def test_strategy_service_falls_back_when_llm_fails() -> None:
    service = StrategyAnalysisService(llm_client=FailingLLMClient())

    response = service.analyze(
        StrategyAnalysisRequest(
            question="Should Ferrari pit under safety car?",
            race_context={"tyre_age": 18},
        )
    )

    assert response.confidence == "low"
    assert "进站" in response.recommendation
