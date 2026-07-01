from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.news import NewsArticleRead


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
