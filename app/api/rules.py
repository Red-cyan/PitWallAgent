from fastapi import APIRouter

from app.schemas.rules import RetrievalDebugResponse, RuleAskRequest, RuleAskResponse
from app.services.qa_service import RegulationQAService

router = APIRouter(prefix="/api/rules", tags=["rules"])
qa_service = RegulationQAService()


@router.post("/ask", response_model=RuleAskResponse)
def ask_rules(request: RuleAskRequest) -> RuleAskResponse:
    return qa_service.ask(request)


@router.post("/retrieve/debug", response_model=RetrievalDebugResponse)
def debug_rule_retrieval(request: RuleAskRequest) -> RetrievalDebugResponse:
    return qa_service.debug_retrieval(request)
