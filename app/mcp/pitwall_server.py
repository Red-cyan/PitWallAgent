"""Model Context Protocol (MCP) server exposing PitWall capabilities.

The server exposes the FIA regulation RAG, live race data, and news search as
standard MCP tools so that any MCP client (Claude Desktop, `mcp inspector`,
cursor, etc.) can call them. Tool functions are plain methods that reuse the
same domain services as the FastAPI layer, keeping a single source of truth.
"""

from __future__ import annotations

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from app.schemas.rules import RetrievalDebugRequest, RuleAskRequest
from app.services.news_service import NewsService
from app.services.qa_service import RegulationQAService
from app.services.race_service import RaceService


class PitWallServer:
    """MCP server binding PitWall domain services as MCP tools."""

    server_name = "pitwall-agent"

    def __init__(
        self,
        qa_service: RegulationQAService | None = None,
        race_service: RaceService | None = None,
        news_service: NewsService | None = None,
    ) -> None:
        self.qa_service = qa_service or RegulationQAService()
        self.race_service = race_service or RaceService()
        self.news_service = news_service or NewsService()
        self.app = FastMCP(self.server_name)
        self._register_tools()

    # ------------------------------------------------------------------ #
    # Tool implementations (plain methods, unit-testable)                #
    # ------------------------------------------------------------------ #

    def regulation_ask(self, question: str, top_k: int = 5) -> dict[str, Any]:
        """Answer an FIA Formula 1 regulation question with cited evidence.

        Runs the full RAG pipeline (retrieval + grounded answer generation)
        and returns the answer together with its citations, answer status and
        confidence. When evidence is insufficient the answer is a deterministic
        refusal instead of a hallucination.
        """
        request = RuleAskRequest(question=question)
        response = self.qa_service.ask(request)
        return {
            "success": True,
            "question": question,
            "answer": response.answer,
            "answer_status": response.answer_status,
            "confidence": response.confidence,
            "evidence_count": response.evidence_count,
            "source_mode": response.source_mode,
            "query_type": response.query_type,
            "citations": [citation.model_dump(mode="json") for citation in response.citations],
        }

    def regulation_debug_retrieval(self, question: str, top_k: int = 5) -> dict[str, Any]:
        """Debug RAG retrieval for an FIA regulation question.

        Returns the normalized question, expanded keywords and the full
        candidate pipeline (keyword / vector / hybrid / reranked) with
        per-chunk scores and score components, useful for diagnosing why a
        chunk was or was not retrieved.
        """
        request = RetrievalDebugRequest(question=question, top_k=top_k)
        response = self.qa_service.debug_retrieval(request, top_k=top_k)
        return {
            "success": True,
            "question": response.question,
            "normalized_question": response.normalized_question,
            "rewritten_queries": response.rewritten_queries,
            "retrieval_queries": response.retrieval_queries,
            "expanded_keywords": response.expanded_keywords,
            "preferred_sections": response.preferred_sections,
            "keyword_candidates": _dump_chunks(response.keyword_candidates),
            "vector_candidates": _dump_chunks(response.vector_candidates),
            "hybrid_candidates": _dump_chunks(response.hybrid_candidates),
            "retrieved_chunks": _dump_chunks(response.retrieved_chunks),
        }

    def race_schedule(self, season: str = "current") -> dict[str, Any]:
        """List the Formula 1 race calendar for a season."""
        schedule = self.race_service.list_schedule(season)
        return {
            "success": True,
            "season": season,
            "races": [race.model_dump(mode="json") for race in schedule],
        }

    def race_next(self, season: str = "current") -> dict[str, Any]:
        """Get the next upcoming Formula 1 race and its sessions."""
        race = self.race_service.get_next_race(season)
        if race is None:
            return {"success": False, "season": season, "error": "No upcoming race found."}
        return {"success": True, "season": season, "race": race.model_dump(mode="json")}

    def race_previous(self, season: str = "current") -> dict[str, Any]:
        """Get the most recently completed Formula 1 race and its sessions."""
        race = self.race_service.get_previous_race(season)
        if race is None:
            return {"success": False, "season": season, "error": "No previous race found."}
        return {"success": True, "season": season, "race": race.model_dump(mode="json")}

    def race_driver_standings(self, season: str = "current") -> dict[str, Any]:
        """Get the current Formula 1 drivers championship standings."""
        standings = self.race_service.list_driver_standings(season)
        return {
            "success": True,
            "season": season,
            "standings": [item.model_dump(mode="json") for item in standings],
        }

    def race_constructor_standings(self, season: str = "current") -> dict[str, Any]:
        """Get the current Formula 1 constructors championship standings."""
        standings = self.race_service.list_constructor_standings(season)
        return {
            "success": True,
            "season": season,
            "standings": [item.model_dump(mode="json") for item in standings],
        }

    def race_results(self, season: str = "current", round_number: int | None = None) -> dict[str, Any]:
        """Get Formula 1 race results for the latest completed round or a given round number."""
        result = self.race_service.get_race_results(season, round_number=round_number)
        if result is None:
            return {"success": False, "season": season, "error": "No completed race results found."}
        return {
            "success": True,
            "season": season,
            "race_result": result.model_dump(mode="json"),
        }

    def news_search(self, query: str, limit: int = 5) -> dict[str, Any]:
        """Search recent Formula 1 news articles by keyword (Chinese aliases supported)."""
        if not query or not query.strip():
            return {"success": False, "error": "News search requires a query."}
        articles = self.news_service.search_articles(query=query, limit=max(1, int(limit)))
        return {
            "success": True,
            "query": query,
            "articles": [article.model_dump(mode="json") for article in articles],
        }

    def news_recent(self, limit: int = 10) -> dict[str, Any]:
        """List the most recent Formula 1 news articles."""
        articles = self.news_service.list_recent_articles(limit=max(1, int(limit)))
        return {
            "success": True,
            "articles": [article.model_dump(mode="json") for article in articles],
        }

    # ------------------------------------------------------------------ #
    # Registration                                                       #
    # ------------------------------------------------------------------ #

    def _register_tools(self) -> None:
        tool_methods = [
            self.regulation_ask,
            self.regulation_debug_retrieval,
            self.race_schedule,
            self.race_next,
            self.race_previous,
            self.race_driver_standings,
            self.race_constructor_standings,
            self.race_results,
            self.news_search,
            self.news_recent,
        ]
        for method in tool_methods:
            self.app.tool()(method)

    def streamable_http_app(self) -> Any:
        """Return the ASGI app for the streamable HTTP transport."""
        return self.app.streamable_http_app()

    def run(self, transport: Literal["stdio", "sse", "streamable-http"] = "stdio") -> None:
        """Run the MCP server over the given transport (stdio by default)."""
        self.app.run(transport=transport)


def _dump_chunks(chunks: list[Any]) -> list[dict[str, Any]]:
    return [chunk.model_dump(mode="json") for chunk in chunks]


def build_server() -> PitWallServer:
    return PitWallServer()


if __name__ == "__main__":
    build_server().run(transport="stdio")
