from __future__ import annotations

import logging

from app.core.logging import log_structured
from app.services.llm.client import LLMClient


class GeneralAnswerService:
    """Handle open-ended F1 questions that do not fit a structured tool."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.logger = logging.getLogger("pitwall.general")
        self.llm_client = llm_client

    def answer(self, question: str) -> dict[str, str]:
        normalized_question = question.strip()
        log_structured(
            self.logger,
            "general_answer_started",
            question_length=len(normalized_question),
        )

        try:
            llm_client = self.llm_client or LLMClient()
            answer = llm_client.chat(
                messages=self._build_messages(normalized_question),
                temperature=0.3,
            ).strip()
            if not answer:
                raise ValueError("Empty LLM answer.")

            log_structured(
                self.logger,
                "general_answer_completed",
                mode="llm",
                answer_length=len(answer),
            )
            return {"answer": answer, "mode": "llm"}
        except Exception as exc:
            answer = self._build_fallback_answer(normalized_question)
            log_structured(
                self.logger,
                "general_answer_completed",
                mode="fallback",
                answer_length=len(answer),
                error_type=exc.__class__.__name__,
            )
            return {"answer": answer, "mode": "fallback"}

    def _build_messages(self, question: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are PitWall, a Formula 1 assistant. "
                    "Answer in concise Chinese. "
                    "Handle open-ended F1 questions such as greetings, driver/team comparisons, "
                    "historical context, racecraft explanations, and general motorsport knowledge. "
                    "Do not invent live standings, schedules, or regulations when you are not sure. "
                    "If a question requires live or authoritative data, say that clearly and suggest asking "
                    "for the latest standings, schedule, news, or regulation lookup."
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ]

    def _build_fallback_answer(self, question: str) -> str:
        lowered = question.lower()
        if any(token in lowered for token in ("你好", "hello", "hi", "hey")):
            return "你好，我可以回答 F1 的新闻、赛程、积分、规则和一般性问题。"

        return (
            "这个问题更适合走通用 F1 问答，但当前通用回答能力不可用。"
            "你可以换一种更具体的问法，例如问某位车手、某支车队、某场比赛，"
            "或者直接问最新积分、赛程、规则。"
        )
