from pydantic import BaseModel, Field


class RuleAskRequest(BaseModel):
    """
    关于FIA规则的提问请求模型

    Attributes:
        question (str): 用户关于FIA规则的问题，长度至少为1个字符
    """
    question: str = Field(..., min_length=1, description="User question about FIA regulations.")


class Citation(BaseModel):
    """
    引用信息，用于标注规则来源的具体文献出处

    Attributes:
        document_title (str): 来源文档的标题
        article (str | None): 条款编号或章节标识符
        section (str | None): 章节标题或小节名称
        page (int | None): 来源文档中的页码，必须大于等于 1
        excerpt (str | None): 来源文档中的支持性摘录文本
    """
    document_title: str = Field(..., description="Title of the source document.")
    article: str | None = Field(default=None, description="Article number or clause identifier.")
    section: str | None = Field(default=None, description="Section title or heading.")
    page: int | None = Field(default=None, ge=1, description="Page number in the source document.")
    excerpt: str | None = Field(default=None, description="Supporting excerpt from the source.")


class RetrievedChunk(BaseModel):
    """
    检索到的文档分块数据模型

    Attributes:
        chunk_id (str): 检索分块的唯一标识符
        content (str): 检索分块的文本内容，长度至少为1
        score (float | None): 检索相关性评分，默认为 None
        document_title (str): 来源文档的标题
        article (str | None): 条款编号或条款标识符，默认为 None
        page (int | None): 来源文档中的页码，须大于等于1，默认为 None
    """
    chunk_id: str = Field(..., description="Unique identifier of the retrieved chunk.")
    content: str = Field(..., min_length=1, description="Retrieved chunk content.")
    score: float | None = Field(default=None, description="Retrieval relevance score.")
    document_title: str = Field(..., description="Title of the source document.")
    article: str | None = Field(default=None, description="Article number or clause identifier.")
    page: int | None = Field(default=None, ge=1, description="Page number in the source document.")


class RuleAskResponse(BaseModel):
    """
    规则问答响应模型，封装对用户问题的回答及相关支撑信息。

    Attributes:
        answer (str): 基于检索内容生成的回答，不可为空。
        citations (list[Citation]): 支撑回答的引用来源列表，默认为空。
        retrieved_chunks (list[RetrievedChunk]): 用于生成回答和调试的检索片段列表，默认为空。
    """
    answer: str = Field(..., min_length=1, description="Grounded answer to the user's question.")
    citations: list[Citation] = Field(default_factory=list, description="Supporting citations.")
    retrieved_chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Retrieved chunks used for answering and debugging.",
    )
