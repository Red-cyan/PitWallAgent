from app.db.engine import SessionLocal
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsArticleRead
from app.services.news_source import NewsSource


class NewsIngestionService:
    """新闻抓取入库服务。"""

    def ingest(self, source: NewsSource, limit: int = 20) -> list[NewsArticleRead]:
        articles = list(source.fetch_articles(limit=limit))

        with SessionLocal() as session:
            repository = NewsRepository(session)
            saved_articles = [repository.upsert_article(article) for article in articles]

        return saved_articles
