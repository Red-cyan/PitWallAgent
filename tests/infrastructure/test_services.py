import os

import pytest
from redis import Redis
from sqlalchemy import create_engine, text

from app.services.session_service import ConversationSession, RedisSessionStore


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INFRA_TESTS") != "1",
    reason="set RUN_INFRA_TESTS=1 with PostgreSQL and Redis available",
)


def test_postgres_migration_is_at_head() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config("alembic.ini"))
    expected_head = script.get_current_head()

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            tables = set(
                connection.scalars(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                )
            )
        assert revision == expected_head, (
            f"database revision {revision!r} is not at head {expected_head!r}"
        )
        assert {"regulation_chunks", "news_articles"} <= tables
    finally:
        engine.dispose()


def test_redis_session_round_trip() -> None:
    client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    store = RedisSessionStore(client=client, ttl_seconds=60)  # type: ignore[arg-type]
    session = ConversationSession(session_id="ci-infrastructure-round-trip")
    try:
        store.save(session)
        loaded = store.get(session.session_id)
        assert loaded is not None
        assert loaded.session_id == session.session_id
    finally:
        store.delete(session.session_id)
        client.close()
