from __future__ import annotations

from app.config.settings import settings
from app.services.rss_source import RSSFeedSource


class MotorsportRSSSource(RSSFeedSource):
    """Motorsport.com F1 新闻 RSS 源（含发布时间与较完整摘要）。"""

    source_name = "motorsport"

    def __init__(self, feed_url: str | None = None, fetcher=None) -> None:
        super().__init__(
            feed_url=feed_url or settings.motorsport_feed_url,
            fetcher=fetcher,
        )
