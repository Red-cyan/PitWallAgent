from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    """统一 Agent 查询请求。"""

    message: str = Field(..., min_length=1, description="User query for the agent runtime.")


class AgentQueryResponse(BaseModel):
    """统一 Agent 查询响应。"""

    intent: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    success: bool
    final_answer: str = Field(..., min_length=1)
    result: dict = Field(default_factory=dict)
    error: str | None = None
