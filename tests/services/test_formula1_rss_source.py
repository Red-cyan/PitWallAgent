from datetime import UTC, datetime

from app.services.formula1_rss_source import Formula1RSSSource


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


def test_formula1_rss_source_parses_articles() -> None:
    source = Formula1RSSSource(fetcher=lambda _: RSS_SAMPLE)

    articles = source.fetch_articles(limit=2)

    assert len(articles) == 2
    assert articles[0].source_name == "formula1"
    assert articles[0].source_article_id == "race-suspended.abc123.html"
    assert articles[0].title == "Race suspended after heavy rain"
    assert articles[0].summary == "The red flag was shown after extreme weather."
    assert articles[0].published_at == datetime(2026, 7, 1, 10, 0, tzinfo=UTC)


def test_formula1_rss_source_respects_limit() -> None:
    source = Formula1RSSSource(fetcher=lambda _: RSS_SAMPLE)

    articles = source.fetch_articles(limit=1)

    assert len(articles) == 1
