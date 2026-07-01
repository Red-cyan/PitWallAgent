from fastapi import APIRouter
from services.llm.client import LLMClient
from services.llm.prompts import SYSTEM_PROMPT

router = APIRouter()
llm = LLMClient()

@router.post("/strategy")
def strategy_analysis(payload: dict):

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": str(payload)}
    ]

    result = llm.chat(messages)

    return {
        "raw": result
    }