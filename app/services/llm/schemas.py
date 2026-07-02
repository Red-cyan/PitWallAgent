from typing import List

from pydantic import BaseModel

class StrategyAdvice(BaseModel):
    decision: str          # e.g. "BOX NOW"
    confidence: float      # 0~1
    reasoning: List[str]   # bullet points
    risk: str              # LOW / MEDIUM / HIGH
