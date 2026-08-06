from __future__ import annotations

import logging

from app.core.logging import log_structured
from app.db.engine import SessionLocal
from app.repositories.news_repository import NewsRepository
from app.schemas.news import NewsArticleRead
from app.services.formula1_rss_source import Formula1RSSSource
from app.services.motorsport_rss_source import MotorsportRSSSource
from app.services.news_source import NewsSource


class NewsIngestionService:
    """多源新闻抓取入库服务（仅 RSS，不抓取 HTML 正文）。"""

    def __init__(self, sources: list[NewsSource] | None = None) -> None:
        self.logger = logging.getLogger("pitwall.news.ingestion")
        self.sources = sources if sources is not None else self._default_sources()

    def ingest(
        self,
        source: NewsSource | list[NewsSource] | None = None,
        limit: int = 20,
    ) -> list[NewsArticleRead]:
        sources = self._resolve_sources(source)
        articles: list = []

        for news_source in sources:
            try:
                fetched = list(news_source.fetch_articles(limit=limit))
            except Exception as exc:
                log_structured(
                    self.logger,
                    "news_source_fetch_failed",
                    source_name=getattr(news_source, "source_name", "unknown"),
                    error_type=exc.__class__.__name__,
                )
                continue
            articles.extend(fetched)

        if not articles:
            return []

        with SessionLocal() as session:
            repository = NewsRepository(session)
            saved_articles = [repository.upsert_article(article) for article in articles]

        log_structured(
            self.logger,
            "news_ingestion_completed",
            fetched_count=len(articles),
            saved_count=len(saved_articles),
        )
        return saved_articles

    def _resolve_sources(
        self,
        source: NewsSource | list[NewsSource] | None,
    ) -> list[NewsSource]:
        if isinstance(source, list):
            return source
        if source is not None:
            return [source]
        return self.sources

    @staticmethod
    def _default_sources() -> list[NewsSource]:
        return [
            MotorsportRSSSource(),
            Formula1RSSSource(),
        ]
