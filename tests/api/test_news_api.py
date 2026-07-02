from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.news import (
    NewsArticleRead,
    NewsEntity,
    NewsInsightResponse,
    NewsRuleAnalysisResponse,
    RuleTopicMatch,
)
from app.schemas.rules import RetrievedChunk


class StubNewsService:
    def list_recent_articles(self, limit: int = 20) -> list[NewsArticleRead]:
        return [
            NewsArticleRead(
                id=1,
                source_name="formula1",
                source_article_id="race-suspended.abc123.html",
                title="Race suspended after heavy rain",
                summary="The red flag was shown after extreme weather.",
                content=None,
                article_url="https://www.formula1.com/en/latest/article/race-suspended.abc123.html",
                author=None,
                published_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
                tags=["red-flag"],
                fetched_at=datetime(2026, 7, 1, 10, 5, tzinfo=UTC),
                is_deleted=False,
            )
        ][:limit]

    def get_article_by_id(self, article_id: int) -> NewsArticleRead | None:
        if article_id != 1:
            return None

        return NewsArticleRead(
            id=1,
            source_name="formula1",
            source_article_id="race-suspended.abc123.html",
            title="Race suspended after heavy rain",
            summary="The red flag was shown after extreme weather.",
            content=None,
            article_url="https://www.formula1.com/en/latest/article/race-suspended.abc123.html",
            author=None,
            published_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            tags=["red-flag"],
            fetched_at=datetime(2026, 7, 1, 10, 5, tzinfo=UTC),
            is_deleted=False,
        )

    def get_article_insights(self, article_id: int) -> NewsInsightResponse | None:
        article = self.get_article_by_id(article_id)
        if article is None:
            return None

        return NewsInsightResponse(
            article=article,
            category_key="race_control",
            category_label="赛会控制与处罚",
            summary="The red flag was shown after extreme weather.",
            key_points=["The red flag was shown after extreme weather."],
            entities=[
                NewsEntity(entity_type="circuit", name="Silverstone"),
            ],
            rule_relevance="direct",
            rule_relevance_reason="新闻直接包含规则或裁判相关术语：red flag",
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
                    title="红旗与比赛暂停",
                    reason="新闻内容命中了关键词：red flag",
                )
            ],
            suggested_questions=["What is the red flag procedure in Formula 1?"],
            related_chunks=[
                RetrievedChunk(
                    chunk_id="chunk-red-flag",
                    content="When the race is suspended, red flags will be shown at all marshal posts.",
                    score=14.0,
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting] - Iss 07 - 2026-06-25",
                    article="B5.14.2",
                    page=47,
                )
            ],
            analysis_summary="这条新闻主要关联 红旗与比赛暂停，已生成规则检索问题并召回 1 个相关规则片段。",
        )


def test_list_news_returns_articles(monkeypatch) -> None:
    from app.api import news

    monkeypatch.setattr(news, "news_service", StubNewsService())
    client = TestClient(app)

    response = client.get("/api/news?limit=5")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["source_name"] == "formula1"
    assert body[0]["title"] == "Race suspended after heavy rain"


def test_get_news_article_returns_detail(monkeypatch) -> None:
    from app.api import news

    monkeypatch.setattr(news, "news_service", StubNewsService())
    client = TestClient(app)

    response = client.get("/api/news/1")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["source_article_id"] == "race-suspended.abc123.html"


def test_get_news_article_returns_404_for_missing_article(monkeypatch) -> None:
    from app.api import news

    monkeypatch.setattr(news, "news_service", StubNewsService())
    client = TestClient(app)

    response = client.get("/api/news/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "News article not found."


def test_news_insights_returns_independent_news_analysis(monkeypatch) -> None:
    from app.api import news

    monkeypatch.setattr(news, "news_service", StubNewsService())
    client = TestClient(app)

    response = client.get("/api/news/1/insights")

    assert response.status_code == 200
    body = response.json()
    assert body["article"]["id"] == 1
    assert body["category_key"] == "race_control"
    assert body["rule_relevance"] == "direct"
    assert body["entities"][0]["name"] == "Silverstone"


def test_news_rules_analysis_returns_linked_rule_data(monkeypatch) -> None:
    from app.api import news

    monkeypatch.setattr(news, "news_service", StubNewsService())
    client = TestClient(app)

    response = client.get("/api/news/1/rules-analysis?top_k=3")

    assert response.status_code == 200
    body = response.json()
    assert body["article"]["id"] == 1
    assert body["matched_topics"][0]["topic_key"] == "red_flag"
    assert body["suggested_questions"] == ["What is the red flag procedure in Formula 1?"]
    assert len(body["related_chunks"]) == 1


def test_news_rules_analysis_returns_404_for_missing_article(monkeypatch) -> None:
    from app.api import news

    monkeypatch.setattr(news, "news_service", StubNewsService())
    client = TestClient(app)

    response = client.get("/api/news/999/rules-analysis")

    assert response.status_code == 404
    assert response.json()["detail"] == "News article not found."
