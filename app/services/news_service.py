from app.db.engine import SessionLocal
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsArticleRead


class NewsService:
    """新闻查询服务。"""

    def list_recent_articles(self, limit: int = 20) -> list[NewsArticleRead]:
        with SessionLocal() as session:
            repository = NewsRepository(session)
            return repository.list_recent_articles(limit=limit)

    def get_article_by_id(self, article_id: int) -> NewsArticleRead | None:
        with SessionLocal() as session:
            repository = NewsRepository(session)
            return repository.get_article_by_id(article_id)
