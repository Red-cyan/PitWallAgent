from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import NewsArticleRecord
from app.schemas.news import NewsArticleCreate, NewsArticleRead


class NewsRepository:
    """新闻数据访问层。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_article(self, article: NewsArticleCreate) -> NewsArticleRead:
        existing = self._find_existing(article)
        if existing is None:
            record = NewsArticleRecord(
                source_name=article.source_name,
                source_article_id=article.source_article_id,
                title=article.title,
                summary=article.summary,
                content=article.content,
                article_url=str(article.article_url),
                author=article.author,
                published_at=article.published_at,
                tags=article.tags,
                raw_payload=article.raw_payload,
            )
            self.session.add(record)
            self.session.commit()
            self.session.refresh(record)
            return NewsArticleRead.from_record(record)

        existing.title = article.title
        existing.summary = article.summary
        existing.content = article.content
        existing.author = article.author
        existing.published_at = article.published_at
        existing.tags = article.tags
        existing.raw_payload = article.raw_payload
        existing.is_deleted = False
        self.session.commit()
        self.session.refresh(existing)
        return NewsArticleRead.from_record(existing)

    def list_recent_articles(self, limit: int = 20) -> list[NewsArticleRead]:
        records = self.session.execute(
            self._base_active_query()
            .order_by(NewsArticleRecord.published_at.desc(), NewsArticleRecord.id.desc())
            .limit(limit)
        ).scalars().all()
        return [NewsArticleRead.from_record(record) for record in records]

    def get_article_by_id(self, article_id: int) -> NewsArticleRead | None:
        record = self.session.execute(
            self._base_active_query().where(NewsArticleRecord.id == article_id)
        ).scalar_one_or_none()
        if record is None:
            return None

        return NewsArticleRead.from_record(record)

    def list_articles_for_backfill(
        self,
        source_name: str,
        limit: int = 20,
        only_missing_content: bool = True,
    ) -> list[NewsArticleRead]:
        query = self._base_active_query().where(NewsArticleRecord.source_name == source_name)
        if only_missing_content:
            query = query.where(NewsArticleRecord.content.is_(None))

        records = self.session.execute(
            query.order_by(NewsArticleRecord.id.desc()).limit(limit)
        ).scalars().all()
        return [NewsArticleRead.from_record(record) for record in records]

    def _find_existing(self, article: NewsArticleCreate) -> NewsArticleRecord | None:
        if article.source_article_id:
            record = self.session.execute(
                select(NewsArticleRecord).where(
                    NewsArticleRecord.source_name == article.source_name,
                    NewsArticleRecord.source_article_id == article.source_article_id,
                )
            ).scalar_one_or_none()
            if record is not None:
                return record

        return self.session.execute(
            select(NewsArticleRecord).where(
                NewsArticleRecord.article_url == str(article.article_url)
            )
        ).scalar_one_or_none()

    def _base_active_query(self) -> Select[tuple[NewsArticleRecord]]:
        return select(NewsArticleRecord).where(NewsArticleRecord.is_deleted.is_(False))
