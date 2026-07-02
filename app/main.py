from fastapi import FastAPI

from app.api.router import router

app = FastAPI(
    title="PitWall Agent",
    version="0.1.0",
    description=(
        "Production-oriented Formula 1 assistant API. "
        "Use /api/chat for session-based conversations. "
        "Use /api/agent/query for low-level agent debugging."
    ),
)

app.include_router(router)
