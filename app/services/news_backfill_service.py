from app.db.engine import SessionLocal
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsArticleRead
from app.services.formula1_rss_source import Formula1RSSSource


class NewsBackfillService:
    """新闻详情回填服务。"""

    def backfill_formula1_articles(
        self,
        limit: int = 20,
        only_missing_content: bool = True,
    ) -> list[NewsArticleRead]:
        source = Formula1RSSSource()

        with SessionLocal() as session:
            repository = NewsRepository(session)
            articles = repository.list_articles_for_backfill(
                source_name=source.source_name,
                limit=limit,
                only_missing_content=only_missing_content,
            )
            updated_articles: list[NewsArticleRead] = []

            for article in articles:
                detail = source.fetch_article_detail(article.article_url)
                merged_article = article.to_create_model(
                    summary=detail["summary"] or article.summary,
                    content=detail["content"] or article.content,
                    author=detail["author"] or article.author,
                    tags=detail["tags"] or article.tags,
                )
                updated_articles.append(repository.upsert_article(merged_article))

        return updated_articles
