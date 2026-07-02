from fastapi import APIRouter
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.api.agent import router as agent_router
from app.api.chat import router as chat_router
from app.api.news import router as news_router
from app.api.race import router as race_router
from app.api.rules import router as rules_router
from app.api.strategy import router as strategy_router
from app.config.settings import settings
from app.db.engine import SessionLocal
from app.db.models import NewsArticleRecord, RegulationChunkRecord

router = APIRouter()


@router.get("/")
def root():
    return {"name": "PitWall Agent"}


@router.get("/health")
def health():
    checks = {
        "database": _check_database(),
        "redis": _check_redis(),
        "llm": {
            "status": "configured" if settings.llm_api_key else "not_configured",
            "model": settings.llm_model,
            "base_url": settings.llm_base_url,
        },
        "rag": _check_rag_data(),
        "news": _check_news_data(),
    }
    overall_status = "ok" if all(item["status"] in {"ok", "configured", "not_configured"} for item in checks.values()) else "degraded"
    return {"status": overall_status, "checks": checks}


def _check_database() -> dict:
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok", "backend": "postgresql+pgvector"}
    except SQLAlchemyError as exc:
        return {"status": "degraded", "backend": "postgresql+pgvector", "error": exc.__class__.__name__}


def _check_redis() -> dict:
    if settings.session_backend.lower() != "redis":
        return {"status": "not_configured", "backend": settings.session_backend}

    try:
        from redis import Redis

        client = Redis.from_url(settings.resolved_redis_url, decode_responses=True)
        client.ping()
        return {"status": "ok", "backend": "redis"}
    except Exception as exc:
        return {"status": "degraded", "backend": "redis", "error": exc.__class__.__name__}


def _check_rag_data() -> dict:
    try:
        with SessionLocal() as session:
            chunk_count = session.scalar(select(func.count(RegulationChunkRecord.id))) or 0
        return {"status": "ok", "chunk_count": chunk_count, "vector_backend": "pgvector"}
    except SQLAlchemyError as exc:
        return {"status": "degraded", "chunk_count": None, "vector_backend": "pgvector", "error": exc.__class__.__name__}


def _check_news_data() -> dict:
    try:
        with SessionLocal() as session:
            article_count = session.scalar(select(func.count(NewsArticleRecord.id))) or 0
        return {"status": "ok", "article_count": article_count}
    except SQLAlchemyError as exc:
        return {"status": "degraded", "article_count": None, "error": exc.__class__.__name__}


router.include_router(rules_router)
router.include_router(news_router)
router.include_router(race_router)
router.include_router(strategy_router)
router.include_router(agent_router)
router.include_router(chat_router)
