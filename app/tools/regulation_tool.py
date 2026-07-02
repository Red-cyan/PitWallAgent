from typing import Any

from app.schemas.rules import RuleAskRequest
from app.services.qa_service import RegulationQAService
from app.tools.base import ToolResult


class RegulationTool:
    """规则工具。"""

    name = "regulation_tool"
    description = "Answer FIA regulation questions and debug regulation retrieval."

    def __init__(self, qa_service: RegulationQAService | None = None) -> None:
        self.qa_service = qa_service or RegulationQAService()

    def invoke(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action")
        question = kwargs.get("question")

        if action not in {"ask", "debug_retrieval"}:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Unsupported regulation tool action: {action}",
            )

        if not isinstance(question, str) or not question.strip():
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Question is required.",
            )

        try:
            request = RuleAskRequest(question=question)

            if action == "ask":
                response = self.qa_service.ask(request)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    payload={
                        "action": action,
                        "response": response.model_dump(mode="json"),
                    },
                )

            response = self.qa_service.debug_retrieval(request)
            return ToolResult(
                tool_name=self.name,
                success=True,
                payload={
                    "action": action,
                    "response": response.model_dump(mode="json"),
                },
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
            )
