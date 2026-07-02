from __future__ import annotations

import logging
from typing import Any

from app.core.logging import log_structured
from app.services.general_answer_service import GeneralAnswerService
from app.tools.base import ToolResult


class GeneralTool:
    """General-purpose F1 answer tool."""

    name = "general_tool"
    description = "Answer open-ended Formula 1 questions with a general LLM fallback."

    def __init__(self, general_answer_service: GeneralAnswerService | None = None) -> None:
        self.logger = logging.getLogger("pitwall.tool.general")
        self.general_answer_service = general_answer_service or GeneralAnswerService()

    def invoke(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action")
        question = kwargs.get("question")
        log_structured(self.logger, "general_tool_invoked", action=action)

        if action != "answer":
            result = ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unsupported general tool action: {action}",
            )
            log_structured(self.logger, "general_tool_completed", action=action, success=result.success)
            return result

        if not isinstance(question, str) or not question.strip():
            result = ToolResult(
                tool_name=self.name,
                success=False,
                error="Question is required.",
            )
            log_structured(self.logger, "general_tool_completed", action=action, success=result.success)
            return result

        try:
            response = self.general_answer_service.answer(question)
            result = ToolResult(
                tool_name=self.name,
                success=True,
                payload={"action": action, "response": response},
            )
            log_structured(self.logger, "general_tool_completed", action=action, success=result.success)
            return result
        except Exception as exc:
            result = ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
            )
            log_structured(
                self.logger,
                "general_tool_completed",
                action=action,
                success=result.success,
                error_type=exc.__class__.__name__,
            )
            return result
