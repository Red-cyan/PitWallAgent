from pydantic import BaseModel, Field


class RuleAskRequest(BaseModel):
    """规则问答请求。"""

    question: str = Field(..., min_length=1, description="User question about FIA regulations.")


class Citation(BaseModel):
    """回答中的引用信息。"""

    document_title: str = Field(..., description="Title of the source document.")
    article: str | None = Field(default=None, description="Article number or clause identifier.")
    section: str | None = Field(default=None, description="Section title or heading.")
    page: int | None = Field(default=None, ge=1, description="Page number in the source document.")
    excerpt: str | None = Field(default=None, description="Supporting excerpt from the source.")


class RetrievedChunk(BaseModel):
    """检索得到的文档片段。"""

    chunk_id: str = Field(..., description="Unique identifier of the retrieved chunk.")
    content: str = Field(..., min_length=1, description="Retrieved chunk content.")
    score: float | None = Field(default=None, description="Retrieval relevance score.")
    document_title: str = Field(..., description="Title of the source document.")
    article: str | None = Field(default=None, description="Article number or clause identifier.")
    page: int | None = Field(default=None, ge=1, description="Page number in the source document.")


class RuleAskResponse(BaseModel):
    """规则问答响应。"""

    answer: str = Field(..., min_length=1, description="Grounded answer to the user's question.")
    citations: list[Citation] = Field(default_factory=list, description="Supporting citations.")
    retrieved_chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Retrieved chunks used for answering and debugging.",
    )


class RetrievalDebugResponse(BaseModel):
    """检索调试响应。"""

    question: str = Field(..., min_length=1, description="Original user question.")
    normalized_question: str = Field(..., min_length=1, description="Question after term normalization.")
    rewritten_queries: list[str] = Field(
        default_factory=list,
        description="Additional retrieval queries produced by the rewrite layer.",
    )
    retrieval_queries: list[str] = Field(
        default_factory=list,
        description="Final retrieval query set used by the repository.",
    )
    extracted_phrases: list[str] = Field(
        default_factory=list,
        description="High-value phrases extracted for scoring.",
    )
    expanded_keywords: list[str] = Field(
        default_factory=list,
        description="Expanded keyword set used in keyword retrieval and reranking.",
    )
    preferred_sections: list[str] = Field(
        default_factory=list,
        description="Sections preferred by routing heuristics.",
    )
    retrieved_chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Final retrieved chunks after merge, filtering, and reranking.",
    )
