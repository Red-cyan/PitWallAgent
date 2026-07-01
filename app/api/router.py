from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root():
    return {"name": "PitWall Agent"}


@router.get("/health")
def health():
    return {"status": "ok"}