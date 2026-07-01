from datetime import UTC, datetime

from app.db.models import Base
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsArticleCreate
from app.services.news_ingestion_service import NewsIngestionService


class StubSource:
    source_name = "formula1"

    def fetch_articles(self, limit: int = 20) -> list[NewsArticleCreate]:
        return [
            NewsArticleCreate(
                source_name="formula1",
                source_article_id="news-001",
                title="Red flag in practice",
                summary="Brief summary.",
                article_url="https://www.formula1.com/en/latest/article/test-1.999.html",
                published_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
            )
        ][:limit]


def test_news_ingestion_service_saves_articles(monkeypatch) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app import db

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    monkeypatch.setattr(db.engine, "SessionLocal", testing_session)
    monkeypatch.setattr("app.services.news_ingestion_service.SessionLocal", testing_session)

    service = NewsIngestionService()
    saved_articles = service.ingest(source=StubSource(), limit=1)

    assert len(saved_articles) == 1
    assert saved_articles[0].title == "Red flag in practice"

    with testing_session() as session:
        repository = NewsRepository(session)
        assert len(repository.list_recent_articles()) == 1
