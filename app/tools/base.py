from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolResult:
    """Result returned by every agent tool."""

    tool_name: str
    success: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Tool(Protocol):
    """Common interface exposed by all agent tools."""

    name: str
    description: str

    def invoke(self, **kwargs: Any) -> ToolResult:
        """Execute the tool."""
        ...
