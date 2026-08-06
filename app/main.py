import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.config.settings import settings
from app.core.logging import configure_logging, log_structured
from app.mcp.pitwall_server import PitWallServer
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.request_context import RequestContextMiddleware

configure_logging()


def _ingest_news_on_startup() -> None:
    from app.services.news_ingestion_service import NewsIngestionService

    logger = logging.getLogger("pitwall.news.startup")
    try:
        service = NewsIngestionService()
        saved = service.ingest(limit=settings.news_ingest_startup_limit)
        log_structured(logger, "news_startup_ingestion_completed", saved_count=len(saved))
    except Exception as exc:
        log_structured(
            logger,
            "news_startup_ingestion_failed",
            error_type=exc.__class__.__name__,
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.news_ingest_on_startup:
        threading.Thread(target=_ingest_news_on_startup, daemon=True).start()
    yield


app = FastAPI(
    title="PitWall Agent",
    version="0.1.0",
    description=(
        "Production-oriented Formula 1 assistant API. "
        "Use /api/chat for session-based conversations. "
        "Use /api/agent/query for low-level agent debugging."
    ),
    lifespan=lifespan,
)

app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.resolved_cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

mcp_server = PitWallServer()
app.mount("/mcp", mcp_server.streamable_http_app())
