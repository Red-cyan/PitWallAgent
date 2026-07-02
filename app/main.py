from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.config.settings import settings
from app.core.logging import configure_logging
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.request_context import RequestContextMiddleware

configure_logging()

app = FastAPI(
    title="PitWall Agent",
    version="0.1.0",
    description=(
        "Production-oriented Formula 1 assistant API. "
        "Use /api/chat for session-based conversations. "
        "Use /api/agent/query for low-level agent debugging."
    ),
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
