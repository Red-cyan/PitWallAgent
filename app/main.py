import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import router
from app.config.settings import settings
from app.core.logging import configure_logging, log_structured
from app.core.request_context import get_request_id
from app.mcp.pitwall_server import PitWallServer
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.api_auth import ApiAuthMiddleware
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


def _warmup_models() -> None:
    """后台预热 embedding / rerank 大模型。

    BGE-M3（约 2.3GB）与 reranker 首次加载需数十秒，若等首个请求
    才同步加载会让第一个法规问答直接卡死；启动时在后台线程预载，
    不阻塞服务就绪。
    """
    logger = logging.getLogger("pitwall.rag.warmup")
    try:
        if settings.regulation_vector_retrieval_enabled:
            from app.rag.embedding.factory import build_embedding_service

            service = build_embedding_service()
            service.embed_texts(["warmup"])
            log_structured(logger, "embedding_warmup_completed")
    except Exception as exc:
        log_structured(
            logger,
            "embedding_warmup_failed",
            error_type=exc.__class__.__name__,
        )
    try:
        if settings.regulation_rerank_enabled:
            from app.rag.rerank.factory import build_reranker

            reranker = build_reranker()
            if reranker is not None:
                reranker.score("warmup", ["warmup"])
                log_structured(logger, "rerank_warmup_completed")
    except Exception as exc:
        log_structured(
            logger,
            "rerank_warmup_failed",
            error_type=exc.__class__.__name__,
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.news_ingest_on_startup:
        threading.Thread(target=_ingest_news_on_startup, daemon=True).start()
    threading.Thread(target=_warmup_models, daemon=True).start()
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
app.add_middleware(ApiAuthMiddleware)

resolved_origins = settings.resolved_cors_allow_origins
if "*" in resolved_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(router)

mcp_server = PitWallServer()
app.mount("/mcp", mcp_server.streamable_http_app())


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    """统一的 HTTP 错误响应，携带 request_id 便于排查。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "request_id": get_request_id(),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed.",
            "errors": exc.errors(),
            "request_id": get_request_id(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    """兜底异常：返回结构化 500，不再暴露 uvicorn 纯文本与堆栈。"""
    logger = logging.getLogger("pitwall.error")
    log_structured(
        logger,
        "unhandled_exception",
        error_type=exc.__class__.__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error.",
            "error_type": exc.__class__.__name__,
            "request_id": get_request_id(),
        },
    )
