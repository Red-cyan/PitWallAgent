from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
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
            try:
                self.session.commit()
            except IntegrityError:
                # 启动抓取线程与手动 refresh 并发时，唯一约束（source_article_id /
                # article_url）可能先被另一方插入；回滚后按已存在记录走更新路径。
                self.session.rollback()
                existing = self._find_existing(article)
                if existing is None:
                    raise
                return self._update_article(existing, article)
            self.session.refresh(record)
            return NewsArticleRead.from_record(record)

        return self._update_article(existing, article)

    def _update_article(
        self, existing: NewsArticleRecord, article: NewsArticleCreate
    ) -> NewsArticleRead:
        existing.title = article.title
        if article.summary is not None:
            existing.summary = article.summary
        if article.content is not None:
            existing.content = article.content
        if article.author is not None:
            existing.author = article.author
        if article.published_at is not None:
            existing.published_at = article.published_at
        if article.tags:
            existing.tags = article.tags
        existing.raw_payload = article.raw_payload
        existing.is_deleted = False
        self.session.commit()
        self.session.refresh(existing)
        return NewsArticleRead.from_record(existing)

    def list_recent_articles(self, limit: int = 20) -> list[NewsArticleRead]:
        records = self.session.execute(
            self._base_active_query()
            .order_by(
                NewsArticleRecord.published_at.desc().nulls_last(),
                NewsArticleRecord.id.desc(),
            )
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

    def search_articles(self, query: str, limit: int = 10) -> list[NewsArticleRead]:
        terms = [term for term in query.split() if term]
        if not terms:
            return []

        conditions = []
        for term in terms[:4]:
            pattern = f"%{term}%"
            conditions.append(
                NewsArticleRecord.title.ilike(pattern)
                | NewsArticleRecord.summary.ilike(pattern)
                | NewsArticleRecord.content.ilike(pattern)
            )

        records = self.session.execute(
            self._base_active_query()
            .where(or_(*conditions))
            .order_by(
                NewsArticleRecord.published_at.desc().nulls_last(),
                NewsArticleRecord.id.desc(),
            )
            .limit(limit)
        ).scalars().all()
        return [NewsArticleRead.from_record(record) for record in records]

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
