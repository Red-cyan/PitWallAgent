from fastapi import APIRouter, HTTPException, Query

from app.schemas.news import NewsArticleRead
from app.services.news_service import NewsService

router = APIRouter(prefix="/api/news", tags=["news"])
news_service = NewsService()


@router.get("", response_model=list[NewsArticleRead])
def list_news(limit: int = Query(default=20, ge=1, le=100)) -> list[NewsArticleRead]:
    return news_service.list_recent_articles(limit=limit)


@router.get("/{article_id}", response_model=NewsArticleRead)
def get_news_article(article_id: int) -> NewsArticleRead:
    article = news_service.get_article_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="News article not found.")

    return article
