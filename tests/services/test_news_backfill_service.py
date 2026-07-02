from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsArticleCreate
from app.services.news_backfill_service import NewsBackfillService


class StubFormula1Source:
    source_name = "formula1"

    def fetch_article_detail(self, article_url: str) -> dict:
        return {
            "summary": "Updated summary.",
            "content": "Updated full content.",
            "author": "F1",
            "tags": ["Silverstone"],
        }


def test_news_backfill_service_updates_existing_article(monkeypatch) -> None:
    from app import db
    from app.services import news_backfill_service

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    monkeypatch.setattr(db.engine, "SessionLocal", testing_session)
    monkeypatch.setattr(news_backfill_service, "SessionLocal", testing_session)
    monkeypatch.setattr(news_backfill_service, "Formula1RSSSource", StubFormula1Source)

    with testing_session() as session:
        repository = NewsRepository(session)
        repository.upsert_article(
            NewsArticleCreate(
                source_name="formula1",
                source_article_id="news-001",
                title="Old title",
                summary="Old summary.",
                content=None,
                article_url="https://www.formula1.com/en/latest/article/test-1.666.html",
                published_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            )
        )

    service = NewsBackfillService()
    updated_articles = service.backfill_formula1_articles(limit=10)

    assert len(updated_articles) == 1
    assert updated_articles[0].summary == "Updated summary."
    assert updated_articles[0].content == "Updated full content."
    assert updated_articles[0].author == "F1"
    assert updated_articles[0].tags == ["Silverstone"]
