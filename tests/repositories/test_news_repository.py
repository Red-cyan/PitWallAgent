from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsArticleCreate


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return testing_session()


def test_upsert_article_inserts_new_record() -> None:
    with build_session() as session:
        repository = NewsRepository(session)

        article = NewsArticleCreate(
            source_name="formula1",
            source_article_id="news-001",
            title="Practice red flag after debris",
            summary="A short summary.",
            content="Longer content here.",
            article_url="https://www.formula1.com/en/latest/article/test-1.123.html",
            author="PitWall",
            published_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
            tags=["practice", "red-flag"],
        )

        saved = repository.upsert_article(article)

        assert saved.id > 0
        assert saved.source_name == "formula1"
        assert saved.tags == ["practice", "red-flag"]


def test_upsert_article_updates_existing_record_by_source_article_id() -> None:
    with build_session() as session:
        repository = NewsRepository(session)

        first = NewsArticleCreate(
            source_name="formula1",
            source_article_id="news-001",
            title="Old title",
            summary="Old summary.",
            article_url="https://www.formula1.com/en/latest/article/test-1.123.html",
        )
        repository.upsert_article(first)

        updated = NewsArticleCreate(
            source_name="formula1",
            source_article_id="news-001",
            title="New title",
            summary="New summary.",
            article_url="https://www.formula1.com/en/latest/article/test-1.123.html",
            tags=["updated"],
        )
        saved = repository.upsert_article(updated)

        assert saved.title == "New title"
        assert saved.summary == "New summary."
        assert saved.tags == ["updated"]
        assert len(repository.list_recent_articles()) == 1


def test_list_recent_articles_orders_by_published_at_desc() -> None:
    with build_session() as session:
        repository = NewsRepository(session)

        repository.upsert_article(
            NewsArticleCreate(
                source_name="formula1",
                source_article_id="news-001",
                title="Earlier",
                article_url="https://www.formula1.com/en/latest/article/test-1.111.html",
                published_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            )
        )
        repository.upsert_article(
            NewsArticleCreate(
                source_name="formula1",
                source_article_id="news-002",
                title="Later",
                article_url="https://www.formula1.com/en/latest/article/test-1.222.html",
                published_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
            )
        )

        articles = repository.list_recent_articles()

        assert [article.title for article in articles] == ["Later", "Earlier"]
