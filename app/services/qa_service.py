import logging
import re

from app.core.logging import log_structured
from app.repositories.rule_repository import RuleRepository
from app.schemas.rules import (
    Citation,
    RetrievalDebugResponse,
    RetrievedChunk,
    RuleAskRequest,
    RuleAskResponse,
)
from app.services.knowledge_service import KnowledgeService
from app.services.llm.client import LLMClient


class RegulationQAService:
    """规则问答服务。"""

    SECTION_SUMMARIES = {
        "Section A": "General Provisions，主要说明锦标赛治理、适用原则、参赛相关定义和总体合规框架。",
        "Section B": "Sporting Regulations，覆盖比赛周末、练习/排位/正赛程序、车手行为、赛事控制、处罚和申诉等竞技规则。",
        "Section C": "Technical Regulations，覆盖赛车尺寸、空气动力、底盘、动力单元相关接口、安全结构和技术合规要求。",
        "Section D": "Financial Regulations (F1 Teams)，覆盖车队成本帽、申报、审计、调整和违规处理。",
        "Section E": "Financial Regulations (Power Unit Manufacturers)，覆盖动力单元制造商成本帽、申报、审查和处罚。",
        "Section F": "Operational Regulations，覆盖测试、运营限制、风洞/仿真、人员与设施等运营要求。",
    }

    def __init__(
        self,
        knowledge_service: KnowledgeService | None = None,
        repository: RuleRepository | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.logger = logging.getLogger("pitwall.regulation")
        self.knowledge_service = knowledge_service or KnowledgeService(
            rule_repository=repository or RuleRepository()
        )
        self.llm_client = llm_client

    def _build_fallback_answer(self, question: str, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return (
                f"未检索到与问题“{question}”相关的 FIA 规则证据。"
                "为了避免编造规则，我不能基于当前资料给出确定答案。"
            )

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
            log_structured(
                self.logger,
                "regulation_answer_fallback_used",
                reason="no_chunks",
                retrieved_chunk_count=0,
            )
            return self._build_fallback_answer(question, chunks)

        try:
            llm_client = self.llm_client or LLMClient()
            messages = self._build_messages(question, chunks)
            answer = llm_client.chat(messages=messages, temperature=0).strip()
            log_structured(
                self.logger,
                "regulation_answer_generated",
                mode="llm",
                retrieved_chunk_count=len(chunks),
            )
            return answer
        except Exception as exc:
            log_structured(
                self.logger,
                "regulation_answer_fallback_used",
                reason="llm_error",
                retrieved_chunk_count=len(chunks),
                error_type=exc.__class__.__name__,
            )
            return self._build_fallback_answer(question, chunks)

    def _build_citations(self, chunks: list[RetrievedChunk]) -> list[Citation]:
        return [
            Citation(
                document_title=chunk.document_title,
                article=chunk.article,
                section=chunk.section,
                page=chunk.page,
                excerpt=chunk.content,
            )
            for chunk in chunks
        ]

    def _has_strong_evidence(self, chunks: list[RetrievedChunk]) -> bool:
        if chunks and all(not chunk.score_components for chunk in chunks):
            return True
        return any(chunk.score_components.get("evidence_strength") == 1.0 for chunk in chunks)

    def _is_unrelated_rule_question(self, question: str) -> bool:
        normalized = question.lower()
        return any(token in normalized for token in ("alien", "extraterrestrial", "ufo")) or "外星" in question

    def _build_partial_evidence_answer(self, question: str, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return self._build_fallback_answer(question, chunks)

        primary = chunks[0]
        article_text = primary.article or "未识别具体条款"
        page_text = f"p.{primary.page}" if primary.page else "page unknown"
        return (
            "我在当前 FIA 规则索引中找到了可能相关的章节，但证据还不够精确，不能直接下确定结论。"
            f" 最接近的依据来自 {primary.document_title}，{article_text}，{page_text}。"
            " 建议把问题再具体到场景、处罚类型或涉及的赛段，我可以继续收窄到更明确的条款。"
        )

    def _classify_query(self, question: str) -> tuple[str, str | None]:
        section_code = self._extract_section_code(question)
        normalized = question.lower()
        overview_tokens = (
            "overview",
            "summary",
            "summarize",
            "what does",
            "about",
            "大体",
            "大概",
            "概览",
            "总览",
            "主要",
            "内容",
            "讲了",
            "讲什么",
            "分几部分",
            "几部分",
        )

        if section_code and any(token in normalized or token in question for token in overview_tokens):
            return "section_overview", section_code

        if any(token in question for token in ("技术规则", "技术规章")) and any(
            token in question for token in ("大概", "概览", "主要", "内容")
        ):
            return "section_overview", "Section C"

        document_tokens = ("大体规则", "规则是什么样", "分几部分", "几部分", "整体", "总览", "概览")
        if any(token in question for token in document_tokens) or (
            "overview" in normalized and ("fia" in normalized or "f1" in normalized or "regulation" in normalized)
        ):
            return "document_overview", None

        return "fact_lookup", None

    def _extract_section_code(self, question: str) -> str | None:
        match = re.search(r"section\s*([a-f])", question, flags=re.IGNORECASE)
        if match:
            return f"Section {match.group(1).upper()}"

        match = re.search(r"第\s*([a-f])\s*(?:部分|章|节)", question, flags=re.IGNORECASE)
        if match:
            return f"Section {match.group(1).upper()}"

        return None

    def _build_section_overview_answer(self, section_code: str, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return f"当前索引中没有 {section_code}，所以不能基于现有资料概括这一部分。"

        summary = self.SECTION_SUMMARIES.get(section_code, "当前索引中有该 Section，但缺少预置摘要。")
        topics = self._extract_overview_topics(chunks, limit=5)
        topic_text = "；".join(topics) if topics else "可从索引中的代表性条款继续追问具体规则。"
        primary = chunks[0]
        article_text = primary.article or "section metadata"
        page_text = f"p.{primary.page}" if primary.page else "page unknown"
        return (
            f"{section_code} 的定位：{summary} "
            f"索引中可见的代表性主题包括：{topic_text}。"
            f"引用：{primary.document_title}，{article_text}，{page_text}。"
        )

    def _build_document_overview_answer(self, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return "当前索引中没有可用于概括 2026 FIA F1 Regulations 的 section 数据。"

        lines = [
            f"{section_code}: {summary}"
            for section_code, summary in self.SECTION_SUMMARIES.items()
            if any((chunk.section == section_code or section_code in chunk.document_title) for chunk in chunks)
        ]
        citation_source = chunks[0]
        citation_text = citation_source.article or "section metadata"
        return (
            "2026 FIA F1 Regulations 当前索引大致分为 Section A-F："
            + " ".join(lines)
            + f" 引用：{citation_source.document_title}，{citation_text}。"
        )

    def _extract_overview_topics(self, chunks: list[RetrievedChunk], limit: int) -> list[str]:
        topics: list[str] = []
        for chunk in chunks:
            heading = chunk.heading_path[-1] if chunk.heading_path else None
            candidate = heading or chunk.article
            if candidate and candidate not in topics:
                topics.append(candidate)
            if len(topics) >= limit:
                break
        return topics

    def ask(self, request: RuleAskRequest) -> RuleAskResponse:
        query_type, section_code = self._classify_query(request.question)
        if self._is_unrelated_rule_question(request.question):
            retrieved_chunks = []
        elif query_type == "section_overview" and section_code is not None:
            retrieved_chunks = self.knowledge_service.rule_repository.get_section_chunks(section_code, limit=6)
        elif query_type == "document_overview":
            retrieved_chunks = self.knowledge_service.rule_repository.get_document_overview_chunks(limit_per_section=1)
        else:
            retrieved_chunks = self.knowledge_service.retrieve_regulation_chunks(request.question)

        log_structured(
            self.logger,
            "regulation_retrieval_completed",
            question_length=len(request.question),
            retrieved_chunk_count=len(retrieved_chunks),
            query_type=query_type,
        )
        has_strong_evidence = self._has_strong_evidence(retrieved_chunks)
        if query_type == "section_overview" and section_code is not None:
            answer = self._build_section_overview_answer(section_code, retrieved_chunks)
        elif query_type == "document_overview":
            answer = self._build_document_overview_answer(retrieved_chunks)
        elif retrieved_chunks and not has_strong_evidence:
            answer = self._build_partial_evidence_answer(request.question, retrieved_chunks)
        else:
            answer = self._generate_answer(request.question, retrieved_chunks)

        citations = self._build_citations(retrieved_chunks)
        if not retrieved_chunks:
            answer_status = "insufficient_evidence"
            confidence = "low"
        elif query_type != "fact_lookup" or has_strong_evidence:
            answer_status = "answered"
            confidence = "medium"
        else:
            answer_status = "partial_evidence"
            confidence = "low"

        return RuleAskResponse(
            answer=answer,
            citations=citations,
            retrieved_chunks=retrieved_chunks,
            answer_status=answer_status,
            confidence=confidence,
            evidence_count=len(retrieved_chunks),
            source_mode="regulation_overview" if query_type != "fact_lookup" else "regulation_rag",
            query_type=query_type,
        )

    def debug_retrieval(self, request: RuleAskRequest) -> RetrievalDebugResponse:
        response = self.knowledge_service.debug_regulation_retrieval(request.question)
        log_structured(
            self.logger,
            "regulation_debug_retrieval_completed",
            question_length=len(request.question),
            retrieved_chunk_count=len(response.retrieved_chunks),
        )
        return response
