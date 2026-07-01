from app.repositories.rule_repository import RuleRepository
from app.schemas.rules import Citation, RetrievedChunk, RuleAskRequest, RuleAskResponse


class RegulationQAService:
    def __init__(self, repository: RuleRepository | None = None) -> None:
        self.repository = repository or RuleRepository()

    def _build_answer(self, question: str, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return f"未检索到与问题“{question}”相关的规则内容。"

        normalized_question = question.lower()
        primary_chunk = chunks[0]

        if "unsafe release" in normalized_question:
            summary = (
                "unsafe release 一般指赛车离开维修区时，以可能危及其他赛车或维修区人员安全的方式被放行。"
            )
        elif "parc ferme" in normalized_question or "parc fermé" in normalized_question:
            summary = (
                "Parc Ferme 指排位赛后至比赛前车辆进入受限状态，只允许进行规则明确允许的操作。"
            )
        elif "plank" in normalized_question or "skid block" in normalized_question:
            summary = (
                "plank 相关规则主要约束底板木板组件的厚度和磨损情况，超出允许磨损范围可能构成技术违规。"
            )
        else:
            summary = "根据当前检索结果，相关规则强调车队和车手在比赛期间必须持续遵守体育和技术规则。"

        return (
            f"{summary} 目前最相关的依据来自 {primary_chunk.document_title} 的 "
            f"{primary_chunk.article}（第 {primary_chunk.page} 页）。"
        )

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
        answer = self._build_answer(request.question, retrieved_chunks)
        citations = self._build_citations(retrieved_chunks)

        return RuleAskResponse(
            answer=answer,
            citations=citations,
            retrieved_chunks=retrieved_chunks,
        )
