from __future__ import annotations

from collections.abc import Callable
from datetime import UTC
from email.utils import parsedate_to_datetime
import re

import feedparser
from bs4 import BeautifulSoup

from app.config.settings import settings
from app.schemas.news import NewsArticleCreate
from app.services.http_retry import get_with_retry


class RSSFeedSource:
    """通用 RSS 订阅源基类。

    只消费站点官方提供的 RSS 元数据（title/summary/link/published），
    不做 HTML 正文抓取，避免反爬限制并保持来源合法稳定。
    """

    source_name = "rss"
    feed_url = ""

    def __init__(
        self,
        feed_url: str | None = None,
        fetcher: Callable[[str], str] | None = None,
    ) -> None:
        self.feed_url = feed_url or self.feed_url
        self.fetcher = fetcher or self._fetch_url

    def fetch_articles(self, limit: int = 20) -> list[NewsArticleCreate]:
        feed_content = self.fetcher(self.feed_url)
        parsed_feed = feedparser.parse(feed_content)
        articles: list[NewsArticleCreate] = []

        for entry in parsed_feed.entries[:limit]:
            article_url = getattr(entry, "link", None)
            title = getattr(entry, "title", "").strip()
            if not article_url or not title:
                continue

            summary = self._clean_html(getattr(entry, "summary", None)) or self._clean_text(title)
            published_at = self._parse_published_at(getattr(entry, "published", None))
            entry_id = getattr(entry, "id", None)
            raw_payload = {
                "id": entry_id,
                "link": article_url,
                "published": getattr(entry, "published", None),
            }

            articles.append(
                NewsArticleCreate(
                    source_name=self.source_name,
                    source_article_id=self._extract_article_id(article_url) or self._as_text(entry_id),
                    title=title,
                    summary=summary,
                    content=None,
                    article_url=article_url,
                    author=self._clean_text(getattr(entry, "author", None)),
                    published_at=published_at,
                    tags=[],
                    raw_payload=raw_payload,
                )
            )

        return articles

    def _fetch_url(self, url: str) -> str:
        response = get_with_retry(
            url,
            provider=f"rss_{self.source_name}",
            headers={"User-Agent": settings.news_user_agent},
            timeout=settings.news_request_timeout_seconds,
            follow_redirects=True,
        )
        return response.text

    @staticmethod
    def _parse_published_at(published: str | None):
        if not published:
            return None
        try:
            parsed = parsedate_to_datetime(published)
        except (TypeError, ValueError, IndexError):
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _extract_article_id(article_url: str) -> str | None:
        path = article_url.split("?", 1)[0].rstrip("/")
        last_segment = path.split("/")[-1]
        return last_segment or None

    @staticmethod
    def _clean_text(text: str | None) -> str | None:
        if text is None:
            return None
        cleaned = " ".join(str(text).split())
        return cleaned or None

    @classmethod
    def _clean_html(cls, text: str | None) -> str | None:
        if text is None:
            return None
        soup = BeautifulSoup(str(text), "html.parser")
        extracted = "\n\n".join(part.strip() for part in soup.stripped_strings)
        return cls._clean_text(extracted)

    @staticmethod
    def _as_text(value) -> str | None:
        if value is None:
            return None
        text = re.sub(r"\s+", " ", str(value)).strip()
        return text or None
