from fastapi import APIRouter, HTTPException, Query

from app.schemas.news import NewsArticleRead, NewsInsightResponse, NewsRuleAnalysisResponse
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


@router.get("/{article_id}/insights", response_model=NewsInsightResponse)
def get_news_article_insights(article_id: int) -> NewsInsightResponse:
    insights = news_service.get_article_insights(article_id)
    if insights is None:
        raise HTTPException(status_code=404, detail="News article not found.")

    return insights


@router.get("/{article_id}/rules-analysis", response_model=NewsRuleAnalysisResponse)
def analyze_news_article_rules(
    article_id: int,
    top_k: int = Query(default=3, ge=1, le=10),
) -> NewsRuleAnalysisResponse:
    analysis = news_service.analyze_article_rules(article_id=article_id, top_k=top_k)
    if analysis is None:
        raise HTTPException(status_code=404, detail="News article not found.")

    return analysis
