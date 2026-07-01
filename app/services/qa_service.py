from app.repositories.rule_repository import RuleRepository
from app.schemas.rules import (
    Citation,
    RetrievalDebugResponse,
    RetrievedChunk,
    RuleAskRequest,
    RuleAskResponse,
)
from app.services.llm.client import LLMClient


class RegulationQAService:
    """规则问答服务。"""

    def __init__(
        self,
        repository: RuleRepository | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.repository = repository or RuleRepository()
        self.llm_client = llm_client

    def _build_fallback_answer(self, question: str, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return f"未检索到与问题“{question}”相关的 FIA 规则内容。"

        primary_chunk = chunks[0]
        article_text = primary_chunk.article or "未识别具体条款"
        page_text = f"第 {primary_chunk.page} 页" if primary_chunk.page else "页码未知"

        return (
            f"根据当前检索结果，最相关的依据来自《{primary_chunk.document_title}》"
            f"的 {article_text}（{page_text}）。"
        )

    def _format_context(self, chunks: list[RetrievedChunk]) -> str:
        context_parts: list[str] = []

        for index, chunk in enumerate(chunks, start=1):
            article_text = chunk.article or "未识别条款"
            page_text = f"第 {chunk.page} 页" if chunk.page else "页码未知"
            score_text = f"{chunk.score:.2f}" if chunk.score is not None else "N/A"
            context_parts.append(
                f"[片段 {index}]\n"
                f"文档: {chunk.document_title}\n"
                f"条款: {article_text}\n"
                f"页码: {page_text}\n"
                f"检索分数: {score_text}\n"
                f"内容:\n{chunk.content}"
            )

        return "\n\n".join(context_parts)

    def _build_messages(self, question: str, chunks: list[RetrievedChunk]) -> list[dict]:
        context = self._format_context(chunks)

        return [
            {
                "role": "system",
                "content": (
                    "你是 PitWall Agent 的 FIA 规则问答助手。"
                    "你必须只根据提供的规则片段回答，不要编造未出现的规则。"
                    "请用简洁中文回答。"
                    "如果证据不足，要明确说明。"
                    "不要输出 markdown 列表。"
                    "引用来源时，只能使用片段中已有的文档名称、条款和页码，不要自行改写来源名称。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题:\n{question}\n\n"
                    f"检索到的规则片段:\n{context}\n\n"
                    "请基于这些片段回答，并在答案末尾简要点出最关键的文档和条款。"
                ),
            },
        ]

    def _generate_answer(self, question: str, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return self._build_fallback_answer(question, chunks)

        try:
            llm_client = self.llm_client or LLMClient()
            messages = self._build_messages(question, chunks)
            return llm_client.chat(messages=messages, temperature=0).strip()
        except Exception:
            return self._build_fallback_answer(question, chunks)

    def _build_citations(self, chunks: list[RetrievedChunk]) -> list[Citation]:
        return [
            Citation(
                document_title=chunk.document_title,
                article=chunk.article,
                section=None,
                page=chunk.page,
                excerpt=chunk.content,
            )
            for chunk in chunks
        ]

    def ask(self, request: RuleAskRequest) -> RuleAskResponse:
        retrieved_chunks = self.repository.search_relevant_chunks(request.question)
        answer = self._generate_answer(request.question, retrieved_chunks)
        citations = self._build_citations(retrieved_chunks)

        return RuleAskResponse(
            answer=answer,
            citations=citations,
            retrieved_chunks=retrieved_chunks,
        )

    def debug_retrieval(self, request: RuleAskRequest) -> RetrievalDebugResponse:
        return self.repository.debug_retrieval(request.question)
