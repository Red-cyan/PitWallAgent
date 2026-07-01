from collections.abc import Callable
from datetime import UTC
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from app.config.settings import settings
from app.schemas.news import NewsArticleCreate


class Formula1RSSSource:
    """Formula1 官方 RSS 新闻源。"""

    source_name = "formula1"

    def __init__(
        self,
        feed_url: str | None = None,
        fetcher: Callable[[str], str] | None = None,
    ) -> None:
        self.feed_url = feed_url or settings.formula1_feed_url
        self.fetcher = fetcher or self._fetch_feed

    def fetch_articles(self, limit: int = 20) -> list[NewsArticleCreate]:
        feed_content = self.fetcher(self.feed_url)
        parsed_feed = feedparser.parse(feed_content)
        articles: list[NewsArticleCreate] = []

        for entry in parsed_feed.entries[:limit]:
            article_url = getattr(entry, "link", None)
            title = getattr(entry, "title", "").strip()
            if not article_url or not title:
                continue

            source_article_id = self._extract_article_id(article_url)
            summary = self._clean_text(getattr(entry, "summary", None))
            published_at = self._parse_published_at(getattr(entry, "published", None))
            raw_payload = {
                "id": getattr(entry, "id", None),
                "link": article_url,
                "published": getattr(entry, "published", None),
            }

            articles.append(
                NewsArticleCreate(
                    source_name=self.source_name,
                    source_article_id=source_article_id,
                    title=title,
                    summary=summary,
                    article_url=article_url,
                    published_at=published_at,
                    raw_payload=raw_payload,
                )
            )

        return articles

    def _fetch_feed(self, feed_url: str) -> str:
        response = httpx.get(
            feed_url,
            headers={"User-Agent": settings.news_user_agent},
            timeout=settings.news_request_timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text

    def _extract_article_id(self, article_url: str) -> str | None:
        last_segment = article_url.rstrip("/").split("/")[-1]
        if not last_segment:
            return None
        return last_segment

    def _parse_published_at(self, published: str | None):
        if not published:
            return None

        try:
            parsed = parsedate_to_datetime(published)
        except (TypeError, ValueError, IndexError):
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC)

    def _clean_text(self, text: str | None) -> str | None:
        if text is None:
            return None

        cleaned = " ".join(text.split())
        return cleaned or None
