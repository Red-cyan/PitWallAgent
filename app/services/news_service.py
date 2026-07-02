from app.db.engine import SessionLocal
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsArticleRead, NewsInsightResponse, NewsRuleAnalysisResponse
from app.services.news_insight_service import NewsInsightService
from app.services.news_rule_analysis_service import NewsRuleAnalysisService


class NewsService:
    """新闻查询服务。"""

    def __init__(
        self,
        insight_service: NewsInsightService | None = None,
        analysis_service: NewsRuleAnalysisService | None = None,
    ) -> None:
        self.insight_service = insight_service or NewsInsightService()
        self.analysis_service = analysis_service or NewsRuleAnalysisService()

    def list_recent_articles(self, limit: int = 20) -> list[NewsArticleRead]:
        with SessionLocal() as session:
            repository = NewsRepository(session)
            return repository.list_recent_articles(limit=limit)

    def get_article_by_id(self, article_id: int) -> NewsArticleRead | None:
        with SessionLocal() as session:
            repository = NewsRepository(session)
            return repository.get_article_by_id(article_id)

    def analyze_article_rules(self, article_id: int, top_k: int = 3) -> NewsRuleAnalysisResponse | None:
        article = self.get_article_by_id(article_id)
        if article is None:
            return None

        return self.analysis_service.analyze(article=article, top_k=top_k)

    def get_article_insights(self, article_id: int) -> NewsInsightResponse | None:
        article = self.get_article_by_id(article_id)
        if article is None:
            return None

        return self.insight_service.analyze(article)
