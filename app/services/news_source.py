from collections.abc import Iterable
from typing import Protocol

from app.schemas.news import NewsArticleCreate


class NewsSource(Protocol):
    """Provider interface for normalized news ingestion."""

    source_name: str

    def fetch_articles(self, limit: int = 20) -> Iterable[NewsArticleCreate]:
        """Fetch normalized articles from the source."""
        ...
