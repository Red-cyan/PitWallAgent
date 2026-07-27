from fastapi import APIRouter, HTTPException

from app.schemas.rules import (
    ActiveCorpusResponse,
    RetrievalDebugRequest,
    RetrievalDebugResponse,
    RuleAskRequest,
    RuleAskResponse,
)
from app.services.qa_service import RegulationQAService

router = APIRouter(prefix="/api/rules", tags=["rules"])
qa_service = RegulationQAService()


@router.post("/ask", response_model=RuleAskResponse)
def ask_rules(request: RuleAskRequest) -> RuleAskResponse:
    return qa_service.ask(request)


@router.post("/retrieve/debug", response_model=RetrievalDebugResponse)
def debug_rule_retrieval(request: RetrievalDebugRequest) -> RetrievalDebugResponse:
    return qa_service.debug_retrieval(request)


@router.get("/corpus/active", response_model=ActiveCorpusResponse)
def get_active_corpus() -> ActiveCorpusResponse:
    corpus = qa_service.knowledge_service.get_active_corpus()
    if corpus is None:
        raise HTTPException(status_code=503, detail="No active regulation corpus is available.")
    return corpus
