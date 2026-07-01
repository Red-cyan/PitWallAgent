from fastapi import APIRouter

from app.schemas.rules import Citation, RetrievedChunk, RuleAskRequest, RuleAskResponse

router = APIRouter()


@router.get("/")
def root():
    return {"name": "PitWall Agent"}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/api/rules/ask", response_model=RuleAskResponse)
def ask_rules(request: RuleAskRequest) -> RuleAskResponse:
    return RuleAskResponse(
        answer=f"这是一个 mock 响应。你问的是：{request.question}",
        citations=[
            Citation(
                document_title="FIA Formula One Sporting Regulations",
                article="Example Article 1.1",
                section="General Principles",
                page=1,
                excerpt="This is a mock citation excerpt for schema and API validation.",
            )
        ],
        retrieved_chunks=[
            RetrievedChunk(
                chunk_id="mock-chunk-001",
                content="This is a mock retrieved chunk used to validate the API response structure.",
                score=0.95,
                document_title="FIA Formula One Sporting Regulations",
                article="Example Article 1.1",
                page=1,
            )
        ],
    )
