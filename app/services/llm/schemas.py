from pydantic import BaseModel
from typing import List, Optional

class StrategyAdvice(BaseModel):
    decision: str          # e.g. "BOX NOW"
    confidence: float      # 0~1
    reasoning: List[str]   # bullet points
    risk: str              # LOW / MEDIUM / HIGH