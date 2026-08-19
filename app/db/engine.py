from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import settings


engine = create_engine(
    settings.sqlalchemy_database_url,
    future=True,
    # Postgres 重启后连接池中的旧连接已失效，pool_pre_ping 让首个请求
    # 自动检测并重建连接，避免重启后第一批请求直接 OperationalError。
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db_session() -> Generator[Session, None, None]:
    """提供数据库会话。"""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
