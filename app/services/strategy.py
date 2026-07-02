from __future__ import annotations

import json
import logging

from app.core.logging import log_structured
from app.schemas.strategy import StrategyAnalysisRequest, StrategyAnalysisResponse
from app.services.knowledge_service import KnowledgeService
from app.services.llm.client import LLMClient
from app.services.news_service import NewsService
from app.services.race_service import RaceService


class StrategyAnalysisService:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        race_service: RaceService | None = None,
        news_service: NewsService | None = None,
        knowledge_service: KnowledgeService | None = None,
    ) -> None:
        self.logger = logging.getLogger("pitwall.strategy")
        self.llm_client = llm_client
        self.race_service = race_service
        self.news_service = news_service
        self.knowledge_service = knowledge_service

    def analyze(self, request: StrategyAnalysisRequest) -> StrategyAnalysisResponse:
        enriched_request = self._enrich_request(request)
        log_structured(
            self.logger,
            "strategy_analysis_started",
            question_length=len(enriched_request.question),
            race_context_keys=list(enriched_request.race_context.keys()),
            regulation_context_count=len(enriched_request.regulation_context),
            news_context_count=len(enriched_request.news_context),
        )

        try:
            llm_client = self.llm_client or LLMClient()
            messages = self._build_messages(enriched_request)
            raw_response = llm_client.chat(messages=messages, temperature=0.1)
            parsed = self._parse_response(enriched_request.question, raw_response)
            log_structured(
                self.logger,
                "strategy_analysis_completed",
                mode="llm",
                confidence=parsed.confidence,
            )
            return parsed
        except Exception as exc:
            fallback = self._build_fallback_response(enriched_request)
            log_structured(
                self.logger,
                "strategy_analysis_completed",
                mode="fallback",
                confidence=fallback.confidence,
                error_type=exc.__class__.__name__,
            )
            return fallback

    def _enrich_request(self, request: StrategyAnalysisRequest) -> StrategyAnalysisRequest:
        race_context = dict(request.race_context)
        regulation_context = list(request.regulation_context)
        news_context = list(request.news_context)

        if self.race_service is not None:
            try:
                if "next_race" not in race_context:
                    next_race = self.race_service.get_next_race()
                    if next_race is not None:
                        race_context["next_race"] = next_race.model_dump(mode="json")
                if "previous_race" not in race_context:
                    previous_race = self.race_service.get_previous_race()
                    if previous_race is not None:
                        race_context["previous_race"] = previous_race.model_dump(mode="json")
            except Exception as exc:
                log_structured(
                    self.logger,
                    "strategy_context_enrichment_skipped",
                    source="race",
                    error_type=exc.__class__.__name__,
                )

        if self.knowledge_service is not None and not regulation_context:
            try:
                chunks = self.knowledge_service.retrieve_regulation_chunks(request.question, top_k=3)
                regulation_context = [
                    self._format_regulation_context_item(chunk.document_title, chunk.article, chunk.content)
                    for chunk in chunks
                ]
            except Exception as exc:
                log_structured(
                    self.logger,
                    "strategy_context_enrichment_skipped",
                    source="regulation",
                    error_type=exc.__class__.__name__,
                )

        if self.news_service is not None and not news_context:
            try:
                articles = self.news_service.list_recent_articles(limit=3)
                news_context = [
                    self._format_news_context_item(article.title, article.summary)
                    for article in articles
                ]
            except Exception as exc:
                log_structured(
                    self.logger,
                    "strategy_context_enrichment_skipped",
                    source="news",
                    error_type=exc.__class__.__name__,
                )

        if (
            race_context == request.race_context
            and regulation_context == request.regulation_context
            and news_context == request.news_context
        ):
            return request

        return StrategyAnalysisRequest(
            question=request.question,
            race_context=race_context,
            regulation_context=regulation_context,
            news_context=news_context,
            additional_context=request.additional_context,
        )

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
            facts.append(f"Received {len(request.race_context)} race context items.")
        if request.regulation_context:
            facts.append(f"Received {len(request.regulation_context)} regulation context items.")
        if request.news_context:
            facts.append(f"Received {len(request.news_context)} news context items.")

        analysis.append(
            "The current context does not include enough tyre, traffic, or lap-time data to issue a high-confidence pit instruction."
        )
        analysis.append(
            "A conditional recommendation is safer than a deterministic call when live race variables are incomplete."
        )
        assumptions.append("The supplied context reflects the current race state.")
        cautions.append("A Safety Car, VSC, red flag, or sudden weather change can invalidate this view immediately.")

        return StrategyAnalysisResponse(
            question=request.question,
            recommendation="Combine live tyre degradation, pit-loss window, and track position before committing to the stop.",
            confidence="low",
            facts=facts,
            analysis=analysis,
            assumptions=assumptions,
            cautions=cautions,
        )

    def _format_regulation_context_item(
        self,
        document_title: str,
        article: str | None,
        content: str,
    ) -> str:
        article_text = article or "Unknown article"
        return f"{document_title} | {article_text} | {content}"

    def _format_news_context_item(self, title: str, summary: str | None) -> str:
        if summary:
            return f"{title}: {summary}"
        return title
