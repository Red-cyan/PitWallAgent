from datetime import UTC, datetime

from app.schemas.news import NewsArticleRead
from app.services.news_insight_service import NewsInsightService


def test_news_insight_service_classifies_driver_market_news() -> None:
    service = NewsInsightService()
    article = NewsArticleRead(
        id=1,
        source_name="formula1",
        source_article_id="news-001",
        title="Norris explains if he sees himself as a one-team driver",
        summary="Lando Norris discussed whether he could stay at McLaren for his whole career.",
        content="Lando Norris said McLaren is where he wants to stay and discussed his long-term future.",
        article_url="https://www.formula1.com/en/latest/article/test-1.123.html",
        author="F1",
        published_at=datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        tags=[],
        fetched_at=datetime(2026, 7, 2, 10, 5, tzinfo=UTC),
        is_deleted=False,
    )

    insights = service.analyze(article)

    assert insights.category_key == "driver_market"
    assert insights.rule_relevance == "none"
    assert any(entity.name == "Lando Norris" for entity in insights.entities)
    assert any(entity.name == "McLaren" for entity in insights.entities)


def test_news_insight_service_marks_race_control_news_as_direct_rule_related() -> None:
    service = NewsInsightService()
    article = NewsArticleRead(
        id=2,
        source_name="formula1",
        source_article_id="news-002",
        title="Race suspended after heavy rain",
        summary="The red flag was shown after extreme weather.",
        content="Race control suspended the session with a red flag after heavy rain at Silverstone.",
        article_url="https://www.formula1.com/en/latest/article/test-1.456.html",
        author="F1",
        published_at=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
        tags=["red-flag"],
        fetched_at=datetime(2026, 7, 2, 12, 5, tzinfo=UTC),
        is_deleted=False,
    )

    insights = service.analyze(article)

    assert insights.category_key == "race_control"
    assert insights.rule_relevance == "direct"
    assert any(entity.name == "Silverstone" for entity in insights.entities)
