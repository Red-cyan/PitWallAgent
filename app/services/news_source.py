from collections.abc import Iterable
from typing import Protocol

from app.schemas.news import NewsArticleCreate


class NewsSource(Protocol):
    """新闻源协议。"""

    source_name: str

    def fetch_articles(self, limit: int = 20) -> Iterable[NewsArticleCreate]:
        """抓取并返回标准化新闻。"""
