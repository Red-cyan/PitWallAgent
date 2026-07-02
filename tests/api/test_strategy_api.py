from fastapi.testclient import TestClient

from app.main import app
from app.schemas.strategy import StrategyAnalysisResponse


class StubStrategyService:
    def analyze(self, request) -> StrategyAnalysisResponse:
        return StrategyAnalysisResponse(
            question=request.question,
            recommendation="建议在安全车窗口内进站",
            confidence="medium",
            facts=["当前窗口损失较低"],
            analysis=["安全车阶段可减少进站损失"],
            assumptions=["当前轮胎已经进入衰减阶段"],
            cautions=["若前方车流过密可能丢失位置"],
        )


def test_strategy_analyze_routes_request(monkeypatch) -> None:
    from app.api import strategy

    monkeypatch.setattr(strategy, "strategy_service", StubStrategyService())
    client = TestClient(app)

    response = client.post(
        "/api/strategy/analyze",
        json={
            "question": "Should Ferrari pit under safety car?",
            "race_context": {"tyre_age": 18},
            "regulation_context": ["Safety car delta applies."],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"] == "建议在安全车窗口内进站"
    assert body["confidence"] == "medium"


def test_strategy_analyze_rejects_empty_question() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/strategy/analyze",
        json={"question": ""},
    )

    assert response.status_code == 422
