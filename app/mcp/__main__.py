"""MCP server entry point: `uv run python -m app.mcp`."""

from __future__ import annotations

from app.mcp.pitwall_server import build_server

if __name__ == "__main__":
    build_server().run(transport="stdio")
