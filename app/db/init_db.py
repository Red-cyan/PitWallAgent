from sqlalchemy import text

from app.db.engine import engine
from app.db.models import Base


def init_db() -> None:
    """初始化 pgvector 扩展与基础表结构。"""

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
