import logging
from typing import Any

from app.core.logging import log_structured
from app.services.news_service import NewsService
from app.tools.base import ToolResult


class NewsTool:
    """新闻工具。"""

    name = "news_tool"
    description = "Retrieve Formula 1 news, article details, and independent news insights."

    def __init__(self, news_service: NewsService | None = None) -> None:
        self.logger = logging.getLogger("pitwall.tool.news")
        self.news_service = news_service or NewsService()

    def invoke(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action")
        log_structured(self.logger, "news_tool_invoked", action=action)

        try:
            if action == "list_recent":
                limit = int(kwargs.get("limit", 10))
                articles = self.news_service.list_recent_articles(limit=limit)
                result = ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "articles": [article.model_dump(mode="json") for article in articles],
                    },
                )
                log_structured(
                    self.logger,
                    "news_tool_completed",
                    action=action,
                    success=result.success,
                    article_count=len(result.payload["articles"]),
                )
                return result

            if action == "get_article":
                article_id = int(kwargs["article_id"])
                article = self.news_service.get_article_by_id(article_id)
                if article is None:
                    result = ToolResult(
                        tool_name=self.name,
                        success=False,
                        error="News article not found.",
                    )
                    log_structured(self.logger, "news_tool_completed", action=action, success=result.success)
                    return result
                result = ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "article": article.model_dump(mode="json"),
                    },
                )
                log_structured(self.logger, "news_tool_completed", action=action, success=result.success)
                return result

            if action == "get_insights":
                article_id = int(kwargs["article_id"])
                insights = self.news_service.get_article_insights(article_id)
                if insights is None:
                    result = ToolResult(
                        tool_name=self.name,
                        success=False,
                        error="News article not found.",
                    )
                    log_structured(self.logger, "news_tool_completed", action=action, success=result.success)
                    return result
                result = ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "insights": insights.model_dump(mode="json"),
                    },
                )
                log_structured(self.logger, "news_tool_completed", action=action, success=result.success)
                return result

            result = ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unsupported news tool action: {action}",
            )
            log_structured(self.logger, "news_tool_completed", action=action, success=result.success)
            return result
        except Exception as exc:
            result = ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
            )
            log_structured(
                self.logger,
                "news_tool_completed",
                action=action,
                success=result.success,
                error_type=exc.__class__.__name__,
            )
            return result
