from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolResult:
    """工具执行结果。"""

    tool_name: str
    success: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Tool(Protocol):
    """工具统一接口。"""

    name: str
    description: str

    def invoke(self, **kwargs: Any) -> ToolResult:
        """执行工具。"""
