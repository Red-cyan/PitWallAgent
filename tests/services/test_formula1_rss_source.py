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

ARTICLE_HTML = """
<html>
  <head>
    <meta name="description" content="Detailed story summary.">
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "author": "F1",
        "description": "Detailed story summary."
      }
    </script>
    <meta property="article:tag" content="Silverstone">
    <meta property="article:tag" content="Weather">
  </head>
  <body>
    <main>
      <div>Silverstone</div>
      <div>Weather</div>
      <h1>Race suspended after heavy rain</h1>
      <p>Detailed story summary.</p>
      <p>Jul 1, 2026 10:00am UTC</p>
      <p>First paragraph of the story.</p>
      <p>Second paragraph of the story.</p>
      <p>Related Articles</p>
      <p>Should not be included.</p>
    </main>
  </body>
</html>
"""


def test_formula1_rss_source_parses_articles_with_article_detail() -> None:
    def fetcher(url: str) -> str:
        if url.endswith(".xml"):
            return RSS_SAMPLE
        return ARTICLE_HTML

    source = Formula1RSSSource(fetcher=fetcher)

    articles = source.fetch_articles(limit=2)

    assert len(articles) == 2
    assert articles[0].source_name == "formula1"
    assert articles[0].source_article_id == "race-suspended.abc123.html"
    assert articles[0].title == "Race suspended after heavy rain"
    assert articles[0].summary == "Detailed story summary."
    assert articles[0].author == "F1"
    assert articles[0].tags == ["Silverstone", "Weather"]
    assert articles[0].content == "First paragraph of the story.\n\nSecond paragraph of the story."
    assert articles[0].published_at == datetime(2026, 7, 1, 10, 0, tzinfo=UTC)


def test_formula1_rss_source_falls_back_to_rss_summary_when_article_detail_fails() -> None:
    def fetcher(url: str) -> str:
        if url.endswith(".xml"):
            return RSS_SAMPLE
        raise RuntimeError("detail fetch failed")

    source = Formula1RSSSource(fetcher=fetcher)

    articles = source.fetch_articles(limit=1)

    assert len(articles) == 1
    assert articles[0].summary == "The red flag was shown after extreme weather."
    assert articles[0].author is None
    assert articles[0].content is None
    assert articles[0].tags == []
