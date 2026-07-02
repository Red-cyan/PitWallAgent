from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class NewsArticleCreate(BaseModel):
    """新闻文章创建请求。"""

    source_name: str = Field(..., min_length=1, max_length=64)
    source_article_id: str | None = Field(default=None, max_length=255)
    title: str = Field(..., min_length=1, max_length=512)
    summary: str | None = Field(default=None)
    content: str | None = Field(default=None)
    article_url: HttpUrl
    author: str | None = Field(default=None, max_length=255)
    published_at: datetime | None = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    raw_payload: dict | None = Field(default=None)


class NewsArticleRead(BaseModel):
    """新闻文章读取模型。"""

    id: int
    source_name: str
    source_article_id: str | None
    title: str
    summary: str | None
    content: str | None
    article_url: str
    author: str | None
    published_at: datetime | None
    tags: list[str]
    fetched_at: datetime
    is_deleted: bool

    @classmethod
    def from_record(cls, record) -> "NewsArticleRead":
        return cls(
            id=record.id,
            source_name=record.source_name,
            source_article_id=record.source_article_id,
            title=record.title,
            summary=record.summary,
            content=record.content,
            article_url=record.article_url,
            author=record.author,
            published_at=record.published_at,
            tags=record.tags or [],
            fetched_at=record.fetched_at,
            is_deleted=record.is_deleted,
        )

    def to_create_model(
        self,
        *,
        summary: str | None = None,
        content: str | None = None,
        author: str | None = None,
        tags: list[str] | None = None,
    ) -> NewsArticleCreate:
        return NewsArticleCreate(
            source_name=self.source_name,
            source_article_id=self.source_article_id,
            title=self.title,
            summary=self.summary if summary is None else summary,
            content=self.content if content is None else content,
            article_url=self.article_url,
            author=self.author if author is None else author,
            published_at=self.published_at,
            tags=self.tags if tags is None else tags,
        )
