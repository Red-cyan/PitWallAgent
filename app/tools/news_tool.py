from typing import Any

from app.services.news_service import NewsService
from app.tools.base import ToolResult


class NewsTool:
    """新闻工具。"""

    name = "news_tool"
    description = "Retrieve Formula 1 news, article details, and independent news insights."

    def __init__(self, news_service: NewsService | None = None) -> None:
        self.news_service = news_service or NewsService()

    def invoke(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action")

        try:
            if action == "list_recent":
                limit = int(kwargs.get("limit", 10))
                articles = self.news_service.list_recent_articles(limit=limit)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "articles": [article.model_dump(mode="json") for article in articles],
                    },
                )

            if action == "get_article":
                article_id = int(kwargs["article_id"])
                article = self.news_service.get_article_by_id(article_id)
                if article is None:
                    return ToolResult(
                        tool_name=self.name,
                        success=False,
                        error="News article not found.",
                    )
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "article": article.model_dump(mode="json"),
                    },
                )

            if action == "get_insights":
                article_id = int(kwargs["article_id"])
                insights = self.news_service.get_article_insights(article_id)
                if insights is None:
                    return ToolResult(
                        tool_name=self.name,
                        success=False,
                        error="News article not found.",
                    )
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "insights": insights.model_dump(mode="json"),
                    },
                )

            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unsupported news tool action: {action}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
            )
