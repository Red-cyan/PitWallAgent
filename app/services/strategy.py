from __future__ import annotations

import json
import logging

from app.core.logging import log_structured
from app.schemas.strategy import StrategyAnalysisRequest, StrategyAnalysisResponse
from app.services.llm.client import LLMClient


class StrategyAnalysisService:
    """比赛策略分析服务。"""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.logger = logging.getLogger("pitwall.strategy")
        self.llm_client = llm_client

    def analyze(self, request: StrategyAnalysisRequest) -> StrategyAnalysisResponse:
        log_structured(
            self.logger,
            "strategy_analysis_started",
            question_length=len(request.question),
            race_context_keys=list(request.race_context.keys()),
            regulation_context_count=len(request.regulation_context),
            news_context_count=len(request.news_context),
        )

        try:
            llm_client = self.llm_client or LLMClient()
            messages = self._build_messages(request)
            raw_response = llm_client.chat(messages=messages, temperature=0.1)
            parsed = self._parse_response(request.question, raw_response)
            log_structured(
                self.logger,
                "strategy_analysis_completed",
                mode="llm",
                confidence=parsed.confidence,
            )
            return parsed
        except Exception as exc:
            fallback = self._build_fallback_response(request)
            log_structured(
                self.logger,
                "strategy_analysis_completed",
                mode="fallback",
                confidence=fallback.confidence,
                error_type=exc.__class__.__name__,
            )
            return fallback

    def _build_messages(self, request: StrategyAnalysisRequest) -> list[dict]:
        payload = {
            "question": request.question,
            "race_context": request.race_context,
            "regulation_context": request.regulation_context,
            "news_context": request.news_context,
            "additional_context": request.additional_context,
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are the strategy analysis module for a Formula 1 assistant. "
                    "Return valid JSON with keys: recommendation, confidence, facts, analysis, assumptions, cautions. "
                    "Keep facts grounded in the supplied context. Separate facts from interpretation."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ]

    def _parse_response(self, question: str, raw_response: str) -> StrategyAnalysisResponse:
        data = json.loads(raw_response)
        data["question"] = question
        return StrategyAnalysisResponse.model_validate(data)

    def _build_fallback_response(self, request: StrategyAnalysisRequest) -> StrategyAnalysisResponse:
        facts: list[str] = []
        analysis: list[str] = []
        assumptions: list[str] = []
        cautions: list[str] = []

        if request.race_context:
            facts.append(f"已收到 {len(request.race_context)} 项比赛上下文。")
        if request.regulation_context:
            facts.append(f"已收到 {len(request.regulation_context)} 条规则相关上下文。")
        if request.news_context:
            facts.append(f"已收到 {len(request.news_context)} 条新闻上下文。")

        analysis.append("当前缺少完整的轮胎、窗口、车流和圈速损失数据，无法给出高置信度进站指令。")
        analysis.append("现阶段更适合给出条件性建议，而不是绝对执行指令。")
        assumptions.append("假设提供的上下文代表当前比赛局势。")
        cautions.append("如果出现安全车、红旗或突发降雨，策略判断需要立即刷新。")

        return StrategyAnalysisResponse(
            question=request.question,
            recommendation="建议结合实时轮胎衰减、窗口损失和赛道位置后再决定是否进站。",
            confidence="low",
            facts=facts,
            analysis=analysis,
            assumptions=assumptions,
            cautions=cautions,
        )
