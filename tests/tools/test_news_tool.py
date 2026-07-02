from datetime import UTC, datetime

from app.schemas.news import (
    NewsArticleRead,
    NewsEntity,
    NewsInsightResponse,
    NewsRuleAnalysisResponse,
    RuleTopicMatch,
)
from app.schemas.rules import RetrievedChunk
from app.tools.news_tool import NewsTool


class StubNewsService:
    def list_recent_articles(self, limit: int = 20) -> list[NewsArticleRead]:
        return [
            NewsArticleRead(
                id=1,
                source_name="formula1",
                source_article_id="news-001",
                title="Race suspended after heavy rain",
                summary="The red flag was shown after extreme weather.",
                content=None,
                article_url="https://www.formula1.com/en/latest/article/test-1.123.html",
                author="F1",
                published_at=datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
                tags=["red-flag"],
                fetched_at=datetime(2026, 7, 2, 10, 5, tzinfo=UTC),
                is_deleted=False,
            )
        ][:limit]

    def get_article_by_id(self, article_id: int) -> NewsArticleRead | None:
        if article_id != 1:
            return None
        return self.list_recent_articles(1)[0]

    def get_article_insights(self, article_id: int) -> NewsInsightResponse | None:
        article = self.get_article_by_id(article_id)
        if article is None:
            return None
        return NewsInsightResponse(
            article=article,
            category_key="race_control",
            category_label="Race Control",
            summary=article.summary or article.title,
            key_points=[article.summary or article.title],
            entities=[NewsEntity(entity_type="circuit", name="Silverstone")],
            rule_relevance="direct",
            rule_relevance_reason="Matched red flag terminology.",
        )

    def analyze_article_rules(self, article_id: int, top_k: int = 3) -> NewsRuleAnalysisResponse | None:
        article = self.get_article_by_id(article_id)
        if article is None:
            return None
        return NewsRuleAnalysisResponse(
            article=article,
            matched_topics=[
                RuleTopicMatch(
                    topic_key="red_flag",
                    title="Red Flag Procedure",
                    reason="matched red flag",
                )
            ],
            suggested_questions=["What is the red flag procedure in Formula 1?"],
            related_chunks=[
                RetrievedChunk(
                    chunk_id="chunk-red-flag",
                    content="When the race is suspended, red flags will be shown.",
                    score=12.0,
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting]",
                    article="ARTICLE 57",
                    section="Section B",
                    page=47,
                )
            ],
            analysis_summary="Rule analysis is available.",
        )


def test_news_tool_lists_recent_articles() -> None:
    tool = NewsTool(news_service=StubNewsService())

    result = tool.invoke(action="list_recent", limit=5)

    assert result.success is True
    assert result.payload["action"] == "list_recent"
    assert len(result.payload["articles"]) == 1


def test_news_tool_returns_insights() -> None:
    tool = NewsTool(news_service=StubNewsService())

    result = tool.invoke(action="get_insights", article_id=1)

    assert result.success is True
    assert result.payload["insights"]["category_key"] == "race_control"


def test_news_tool_returns_error_for_missing_article() -> None:
    tool = NewsTool(news_service=StubNewsService())

    result = tool.invoke(action="get_article", article_id=999)

    assert result.success is False
    assert result.error == "News article not found."


def test_news_tool_returns_rules_analysis() -> None:
    tool = NewsTool(news_service=StubNewsService())

    result = tool.invoke(action="get_rules_analysis", article_id=1, top_k=2)

    assert result.success is True
    assert result.payload["rules_analysis"]["matched_topics"][0]["topic_key"] == "red_flag"
