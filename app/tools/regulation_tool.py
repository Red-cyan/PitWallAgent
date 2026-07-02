import logging
from typing import Any

from app.core.logging import log_structured
from app.schemas.rules import RuleAskRequest
from app.services.qa_service import RegulationQAService
from app.tools.base import ToolResult


class RegulationTool:
    """规则工具。"""

    name = "regulation_tool"
    description = "Answer FIA regulation questions and debug regulation retrieval."

    def __init__(self, qa_service: RegulationQAService | None = None) -> None:
        self.logger = logging.getLogger("pitwall.tool.regulation")
        self.qa_service = qa_service or RegulationQAService()

    def invoke(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action")
        question = kwargs.get("question")
        log_structured(self.logger, "regulation_tool_invoked", action=action)

        if action not in {"ask", "debug_retrieval"}:
            result = ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unsupported regulation tool action: {action}",
            )
            log_structured(self.logger, "regulation_tool_completed", action=action, success=result.success)
            return result

        if not isinstance(question, str) or not question.strip():
            result = ToolResult(
                tool_name=self.name,
                success=False,
                error="Question is required.",
            )
            log_structured(self.logger, "regulation_tool_completed", action=action, success=result.success)
            return result

        try:
            request = RuleAskRequest(question=question)

            if action == "ask":
                response = self.qa_service.ask(request)
                result = ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "response": response.model_dump(mode="json"),
                    },
                )
                log_structured(self.logger, "regulation_tool_completed", action=action, success=result.success)
                return result

            response = self.qa_service.debug_retrieval(request)
            result = ToolResult(
                tool_name=self.name,
                success=True,
                payload={
                    "action": action,
                    "response": response.model_dump(mode="json"),
                },
            )
            log_structured(self.logger, "regulation_tool_completed", action=action, success=result.success)
            return result
        except Exception as exc:
            result = ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
            )
            log_structured(
                self.logger,
                "regulation_tool_completed",
                action=action,
                success=result.success,
                error_type=exc.__class__.__name__,
            )
            return result
