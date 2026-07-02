from fastapi import APIRouter

from app.api.agent import router as agent_router
from app.api.news import router as news_router
from app.api.rules import router as rules_router

router = APIRouter()


@router.get("/")
def root():
    return {"name": "PitWall Agent"}


@router.get("/health")
def health():
    return {"status": "ok"}


router.include_router(rules_router)
router.include_router(news_router)
router.include_router(agent_router)
