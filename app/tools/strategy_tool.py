import logging
from typing import Any

from app.core.logging import log_structured
from app.schemas.strategy import StrategyAnalysisRequest
from app.services.knowledge_service import KnowledgeService
from app.services.news_service import NewsService
from app.services.race_service import RaceService
from app.services.strategy import StrategyAnalysisService
from app.tools.base import ToolResult


class StrategyTool:
    """策略分析工具。"""

    name = "strategy_tool"
    description = "Analyze Formula 1 strategy questions using available race, rule, and news context."

    def __init__(self, strategy_service: StrategyAnalysisService | None = None) -> None:
        self.logger = logging.getLogger("pitwall.tool.strategy")
        self.strategy_service = strategy_service or StrategyAnalysisService(
            race_service=RaceService(),
            news_service=NewsService(),
            knowledge_service=KnowledgeService(),
        )

    def invoke(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action")
        log_structured(self.logger, "strategy_tool_invoked", action=action)

        if action != "analyze":
            result = ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unsupported strategy tool action: {action}",
            )
            log_structured(self.logger, "strategy_tool_completed", action=action, success=result.success)
            return result

        question = kwargs.get("question")
        if not isinstance(question, str) or not question.strip():
            result = ToolResult(
                tool_name=self.name,
                success=False,
                error="Question is required.",
            )
            log_structured(self.logger, "strategy_tool_completed", action=action, success=result.success)
            return result

        try:
            request = StrategyAnalysisRequest(
                question=question,
                race_context=kwargs.get("race_context", {}),
                regulation_context=kwargs.get("regulation_context", []),
                news_context=kwargs.get("news_context", []),
                additional_context=kwargs.get("additional_context"),
            )
            response = self.strategy_service.analyze(request)
            result = ToolResult(
                tool_name=self.name,
                success=True,
                payload={
                    "action": action,
                    "response": response.model_dump(mode="json"),
                },
            )
            log_structured(self.logger, "strategy_tool_completed", action=action, success=result.success)
            return result
        except Exception as exc:
            result = ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
            )
            log_structured(
                self.logger,
                "strategy_tool_completed",
                action=action,
                success=result.success,
                error_type=exc.__class__.__name__,
            )
            return result
