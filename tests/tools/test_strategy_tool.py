from app.tools.strategy_tool import StrategyTool


class StubStrategyService:
    def analyze(self, request):
        from app.schemas.strategy import StrategyAnalysisResponse

        return StrategyAnalysisResponse(
            question=request.question,
            recommendation="建议在安全车窗口内进站",
            confidence="medium",
            facts=["当前窗口损失较低"],
            analysis=["安全车阶段可减少进站损失"],
            assumptions=["当前轮胎已经进入衰减阶段"],
            cautions=["若前方车流过密可能丢失位置"],
        )


def test_strategy_tool_returns_analysis() -> None:
    tool = StrategyTool(strategy_service=StubStrategyService())

    result = tool.invoke(action="analyze", question="Should Ferrari pit under safety car?")

    assert result.success is True
    assert result.payload["response"]["recommendation"] == "建议在安全车窗口内进站"


def test_strategy_tool_rejects_missing_question() -> None:
    tool = StrategyTool(strategy_service=StubStrategyService())

    result = tool.invoke(action="analyze", question="")

    assert result.success is False
    assert result.error == "Question is required."
