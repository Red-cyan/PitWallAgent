from collections.abc import Callable
from datetime import UTC
from email.utils import parsedate_to_datetime
import json
import re

from bs4 import BeautifulSoup
import feedparser
import httpx

from app.config.settings import settings
from app.schemas.news import NewsArticleCreate


class Formula1RSSSource:
    """Formula1 官方 RSS 新闻源。"""

    source_name = "formula1"
    ARTICLE_STATE_PATTERN = re.compile(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        re.DOTALL,
    )
    JSON_LD_ARTICLE_TYPE = "NewsArticle"

    def __init__(
        self,
        feed_url: str | None = None,
        fetcher: Callable[[str], str] | None = None,
    ) -> None:
        self.feed_url = feed_url or settings.formula1_feed_url
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

            detail = self._fetch_article_detail(article_url)
            source_article_id = self._extract_article_id(article_url)
            summary = detail["summary"] or self._clean_text(getattr(entry, "summary", None))
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
                    content=detail["content"],
                    article_url=article_url,
                    author=detail["author"],
                    published_at=published_at,
                    tags=detail["tags"],
                    raw_payload=raw_payload,
                )
            )

        return articles

    def fetch_article_detail(self, article_url: str) -> dict:
        return self._fetch_article_detail(article_url)

    def _fetch_url(self, url: str) -> str:
        response = httpx.get(
            url,
            headers={"User-Agent": settings.news_user_agent},
            timeout=settings.news_request_timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text

    def _fetch_article_detail(self, article_url: str) -> dict:
        try:
            html = self.fetcher(article_url)
            return self._parse_article_detail(html)
        except Exception:
            return {
                "summary": None,
                "content": None,
                "author": None,
                "tags": [],
            }

    def _parse_article_detail(self, html: str) -> dict:
        json_ld_detail = self._parse_json_ld_article(html)
        next_data_match = self.ARTICLE_STATE_PATTERN.search(html)
        if next_data_match:
            detail = self._parse_next_data(next_data_match.group(1))
            merged_detail = self._merge_detail(json_ld_detail, detail)
            if self._has_detail(merged_detail):
                return merged_detail

        html_detail = self._parse_article_html(html)
        return self._merge_detail(json_ld_detail, html_detail)

    def _parse_json_ld_article(self, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            payload = script.string or script.get_text()
            if not payload:
                continue

            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue

            article = self._find_json_ld_article(data)
            if not article:
                continue

            author_value = article.get("author")
            if isinstance(author_value, dict):
                author = self._clean_text(author_value.get("name"))
            else:
                author = self._clean_text(author_value)

            tags = self._extract_tags(article.get("keywords"))
            return {
                "summary": self._clean_text(article.get("description")),
                "content": self._clean_html_text(article.get("articleBody")),
                "author": author,
                "tags": tags,
            }

        return {"summary": None, "content": None, "author": None, "tags": []}

    def _find_json_ld_article(self, data):
        if isinstance(data, dict):
            article_type = data.get("@type")
            if article_type == self.JSON_LD_ARTICLE_TYPE:
                return data
            for value in data.values():
                found = self._find_json_ld_article(value)
                if found:
                    return found
        elif isinstance(data, list):
            for item in data:
                found = self._find_json_ld_article(item)
                if found:
                    return found
        return None

    def _parse_next_data(self, payload: str) -> dict:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {"summary": None, "content": None, "author": None, "tags": []}

        article = self._find_article_node(data)
        if not article:
            return {"summary": None, "content": None, "author": None, "tags": []}

        summary = self._clean_text(article.get("metaDescription") or article.get("description"))
        body = self._extract_body_from_article_node(article)
        author = self._clean_text(article.get("author"))
        tags = self._extract_tags(article.get("tags"))

        return {
            "summary": summary,
            "content": body,
            "author": author,
            "tags": tags,
        }

    def _find_article_node(self, data: dict) -> dict | None:
        candidates: list[dict] = []

        def walk(node):
            if isinstance(node, dict):
                if any(key in node for key in ("body", "metaDescription", "description")):
                    candidates.append(node)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(data)
        return candidates[0] if candidates else None

    def _extract_body_from_article_node(self, article: dict) -> str | None:
        body = article.get("body")
        if isinstance(body, str):
            return self._clean_html_text(body)

        if isinstance(body, list):
            parts = [self._clean_html_text(part) for part in body if isinstance(part, str)]
            combined = "\n\n".join(part for part in parts if part)
            return combined or None

        return None

    def _parse_article_html(self, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        summary = self._clean_text(self._read_meta_content(soup, "description"))
        author = self._clean_text(self._read_meta_content(soup, "author"))
        tags = self._extract_tags_from_html(soup)
        content = self._extract_article_body_from_html(soup, summary=summary)

        return {
            "summary": summary,
            "content": content,
            "author": author,
            "tags": tags,
        }

    def _read_meta_content(self, soup: BeautifulSoup, name: str) -> str | None:
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": f"og:{name}"})
        if tag is None:
            return None

        content = tag.get("content")
        if not isinstance(content, str):
            return None

        return content

    def _extract_tags_from_html(self, soup: BeautifulSoup) -> list[str]:
        tags: list[str] = []
        for tag in soup.find_all("meta", attrs={"property": "article:tag"}):
            content = tag.get("content")
            if isinstance(content, str):
                cleaned = self._clean_text(content)
                if cleaned and cleaned not in tags:
                    tags.append(cleaned)
        return tags

    def _extract_article_body_from_html(self, soup: BeautifulSoup, summary: str | None) -> str | None:
        selectors = [
            '[data-testid="article-body"]',
            "article",
            "main article",
        ]

        for selector in selectors:
            node = soup.select_one(selector)
            if node is None:
                continue

            paragraphs = [self._clean_text(text) for text in node.stripped_strings]
            content = "\n\n".join(text for text in paragraphs if text)
            if content:
                return content

        main_node = soup.find("main")
        if main_node is None:
            return None

        text_parts = [self._clean_text(text) for text in main_node.stripped_strings]
        normalized_parts = [part for part in text_parts if part]
        if not normalized_parts:
            return None

        body_parts = self._trim_main_text_parts(normalized_parts, summary=summary)
        if not body_parts:
            return None

        return "\n\n".join(body_parts)

    def _trim_main_text_parts(self, parts: list[str], summary: str | None) -> list[str]:
        start_index = 0
        if summary and summary in parts:
            start_index = parts.index(summary) + 2

        body_parts: list[str] = []
        for part in parts[start_index:]:
            if self._is_stop_marker(part):
                break
            if self._should_skip_part(part):
                continue
            body_parts.append(part)

        return body_parts

    def _should_skip_part(self, part: str) -> bool:
        if len(part) < 20:
            return True
        if part in {"Show more tags", "READ MORE:", "Related Articles"}:
            return True
        if part.startswith("Jun ") or part.startswith("Jul ") or part.startswith("Aug "):
            return True
        return False

    def _is_stop_marker(self, part: str) -> bool:
        stop_markers = (
            "READ MORE:",
            "Related Articles",
            "More news",
            "More videos",
            "Latest News",
            "Latest Video",
            "Feature",
            "Gallery",
        )
        return any(marker == part for marker in stop_markers)

    def _extract_tags(self, value) -> list[str]:
        if isinstance(value, str):
            candidates = re.split(r"[,|]", value)
        elif isinstance(value, list):
            candidates = value
        else:
            return []

        tags: list[str] = []
        for item in candidates:
            if isinstance(item, str):
                cleaned = self._clean_text(item)
            elif isinstance(item, dict):
                cleaned = self._clean_text(item.get("name") or item.get("label"))
            else:
                cleaned = None

            if cleaned and cleaned not in tags:
                tags.append(cleaned)

        return tags

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

    def _clean_html_text(self, text: str | None) -> str | None:
        if text is None:
            return None

        soup = BeautifulSoup(text, "html.parser")
        extracted = "\n\n".join(part.strip() for part in soup.stripped_strings)
        return self._clean_text(extracted)

    def _merge_detail(self, primary: dict, secondary: dict) -> dict:
        return {
            "summary": primary.get("summary") or secondary.get("summary"),
            "content": primary.get("content") or secondary.get("content"),
            "author": primary.get("author") or secondary.get("author"),
            "tags": primary.get("tags") or secondary.get("tags") or [],
        }

    def _has_detail(self, detail: dict) -> bool:
        return bool(detail["summary"] or detail["content"] or detail["author"] or detail["tags"])
