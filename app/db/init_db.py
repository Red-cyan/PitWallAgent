from sqlalchemy import text

from app.db.engine import engine
from app.db.models import Base


def init_db() -> None:
    """初始化数据库扩展、基础表结构和轻量兼容迁移。"""

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
    _apply_compatible_migrations()


def _apply_compatible_migrations() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                ALTER TABLE IF EXISTS news_articles
                ALTER COLUMN source_article_id TYPE VARCHAR(255)
                """
            )
        )
