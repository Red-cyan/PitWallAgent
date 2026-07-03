from pydantic import BaseModel, Field


class RuleAskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question about FIA regulations.")


class Citation(BaseModel):
    document_title: str = Field(..., description="Title of the source document.")
    article: str | None = Field(default=None, description="Article number or clause identifier.")
    section: str | None = Field(default=None, description="Section title or heading.")
    page: int | None = Field(default=None, ge=1, description="Page number in the source document.")
    excerpt: str | None = Field(default=None, description="Supporting excerpt from the source.")


class RetrievedChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique identifier of the retrieved chunk.")
    content: str = Field(..., min_length=1, description="Retrieved chunk content.")
    score: float | None = Field(default=None, description="Retrieval relevance score.")
    document_title: str = Field(..., description="Title of the source document.")
    article: str | None = Field(default=None, description="Article number or clause identifier.")
    section: str | None = Field(default=None, description="High-level regulation section code.")
    page: int | None = Field(default=None, ge=1, description="Page number in the source document.")
    page_start: int | None = Field(default=None, ge=1, description="First source page covered by this chunk.")
    page_end: int | None = Field(default=None, ge=1, description="Last source page covered by this chunk.")
    heading_path: list[str] = Field(default_factory=list, description="Section/article heading path.")
    score_components: dict[str, float] = Field(
        default_factory=dict,
        description="Explainable retrieval/rerank score components.",
    )


class RuleAskResponse(BaseModel):
    answer: str = Field(..., min_length=1, description="Grounded answer to the user's question.")
    citations: list[Citation] = Field(default_factory=list, description="Supporting citations.")
    retrieved_chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Retrieved chunks used for answering and debugging.",
    )
    answer_status: str = Field(default="answered", description="answered, partial_evidence, or insufficient_evidence.")
    confidence: str = Field(default="medium", description="Answer confidence derived from retrieval quality.")
    evidence_count: int = Field(default=0, ge=0, description="Number of evidence chunks used.")
    source_mode: str = Field(default="regulation_rag", description="Source path used to build the answer.")
    query_type: str = Field(default="fact_lookup", description="fact_lookup, section_overview, or document_overview.")


class RetrievalDebugResponse(BaseModel):
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
    vector_candidates: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Candidates returned by vector retrieval before hybrid fusion.",
    )
    keyword_candidates: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Candidates returned by keyword/BM25 retrieval before hybrid fusion.",
    )
    hybrid_candidates: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Candidates after hybrid fusion before final rerank.",
    )
    retrieved_chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Final retrieved chunks after merge, filtering, and reranking.",
    )
