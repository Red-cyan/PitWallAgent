from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.agent import AgentQueryResponse


class ConversationTurn(BaseModel):
    """单轮会话记录。"""

    role: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    created_at: datetime
    intent: str | None = None
    tool_name: str | None = None


class ChatRequest(BaseModel):
    """聊天请求。"""

    message: str = Field(..., min_length=1)
    session_id: str | None = Field(default=None, min_length=1)


class ChatResponse(BaseModel):
    """聊天响应。"""

    session_id: str = Field(..., min_length=1)
    response: AgentQueryResponse
    history: list[ConversationTurn] = Field(default_factory=list)
