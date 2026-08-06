from datetime import UTC, datetime

from app.services.formula1_rss_source import Formula1RSSSource
from app.services.motorsport_rss_source import MotorsportRSSSource


RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Formula1 Latest</title>
    <item>
      <title>Race suspended after heavy rain</title>
      <link>https://www.formula1.com/en/latest/article/race-suspended.abc123.html</link>
      <pubDate>Wed, 01 Jul 2026 10:00:00 GMT</pubDate>
      <description>The red flag was shown after extreme weather.</description>
      <guid>abc123</guid>
    </item>
    <item>
      <title>Verstappen tops practice</title>
      <link>https://www.formula1.com/en/latest/article/practice-result.def456.html</link>
      <pubDate>Wed, 01 Jul 2026 08:00:00 GMT</pubDate>
      <description>He led the session by two tenths.</description>
      <guid>def456</guid>
    </item>
  </channel>
</rss>
"""


def test_formula1_rss_source_parses_rss_metadata_only() -> None:
    def fetcher(url: str) -> str:
        return RSS_SAMPLE

    source = Formula1RSSSource(fetcher=fetcher)

    articles = source.fetch_articles(limit=2)

    assert len(articles) == 2
    assert articles[0].source_name == "formula1"
    assert articles[0].source_article_id == "race-suspended.abc123.html"
    assert articles[0].title == "Race suspended after heavy rain"
    assert articles[0].summary == "The red flag was shown after extreme weather."
    assert articles[0].content is None
    assert articles[0].author is None
    assert articles[0].tags == []
    assert articles[0].published_at == datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    assert articles[0].article_url == "https://www.formula1.com/en/latest/article/race-suspended.abc123.html"


def test_formula1_rss_source_skips_entries_without_link_or_title() -> None:
    def fetcher(url: str) -> str:
        return RSS_SAMPLE

    source = Formula1RSSSource(fetcher=fetcher)

    articles = source.fetch_articles(limit=1)

    assert len(articles) == 1
    assert articles[0].title == "Race suspended after heavy rain"


def test_motorsport_rss_source_uses_own_source_name() -> None:
    def fetcher(url: str) -> str:
        return RSS_SAMPLE

    source = MotorsportRSSSource(fetcher=fetcher)

    articles = source.fetch_articles(limit=1)

    assert articles[0].source_name == "motorsport"
