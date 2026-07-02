import json
import logging
from datetime import UTC, datetime

from app.schemas.news import NewsArticleRead
from app.schemas.rules import Citation, RetrievalDebugResponse, RetrievedChunk, RuleAskResponse
from app.tools.news_tool import NewsTool
from app.tools.race_tool import RaceTool
from app.tools.regulation_tool import RegulationTool


class StubNewsService:
    def list_recent_articles(self, limit: int = 20) -> list[NewsArticleRead]:
        return [
            NewsArticleRead(
                id=1,
                source_name="formula1",
                source_article_id="news-001",
                title="Race suspended after heavy rain",
                summary="The red flag was shown after extreme weather.",
                content=None,
                article_url="https://www.formula1.com/en/latest/article/test-1.123.html",
                author="F1",
                published_at=datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
                tags=["red-flag"],
                fetched_at=datetime(2026, 7, 2, 10, 5, tzinfo=UTC),
                is_deleted=False,
            )
        ][:limit]


class StubRaceService:
    def list_driver_standings(self, season):
        from app.schemas.race import DriverStandingEntry

        return [
            DriverStandingEntry(position=1, driver_name="Andrea Kimi Antonelli", team_name="Mercedes", points=171, source="stub")
        ]


class StubQAService:
    def ask(self, request) -> RuleAskResponse:
        return RuleAskResponse(
            answer=f"stub answer for: {request.question}",
            citations=[
                Citation(
                    document_title="doc",
                    article="B5.14.2",
                    section=None,
                    page=47,
                    excerpt="Red flags will be shown.",
                )
            ],
            retrieved_chunks=[
                RetrievedChunk(
                    chunk_id="chunk-red-flag",
                    content="Red flags will be shown.",
                    score=14.0,
                    document_title="doc",
                    article="B5.14.2",
                    page=47,
                )
            ],
        )

    def debug_retrieval(self, request) -> RetrievalDebugResponse:
        return RetrievalDebugResponse(
            question=request.question,
            normalized_question=request.question,
            rewritten_queries=[request.question],
            retrieval_queries=[request.question],
            extracted_phrases=[],
            expanded_keywords=[],
            preferred_sections=[],
            retrieved_chunks=[],
        )


def test_news_tool_emits_structured_logs(caplog) -> None:
    tool = NewsTool(news_service=StubNewsService())

    with caplog.at_level(logging.INFO, logger="pitwall.tool.news"):
        result = tool.invoke(action="list_recent", limit=5)

    assert result.success is True
    payloads = [json.loads(record.message) for record in caplog.records if record.name == "pitwall.tool.news"]
    assert payloads[0]["event"] == "news_tool_invoked"
    assert payloads[-1]["event"] == "news_tool_completed"


def test_race_tool_emits_structured_logs(caplog) -> None:
    tool = RaceTool(race_service=StubRaceService())

    with caplog.at_level(logging.INFO, logger="pitwall.tool.race"):
        result = tool.invoke(action="get_driver_standings")

    assert result.success is True
    payloads = [json.loads(record.message) for record in caplog.records if record.name == "pitwall.tool.race"]
    assert payloads[0]["event"] == "race_tool_invoked"
    assert payloads[-1]["event"] == "race_tool_completed"


def test_regulation_tool_emits_structured_logs(caplog) -> None:
    tool = RegulationTool(qa_service=StubQAService())

    with caplog.at_level(logging.INFO, logger="pitwall.tool.regulation"):
        result = tool.invoke(action="ask", question="What is the red flag procedure?")

    assert result.success is True
    payloads = [json.loads(record.message) for record in caplog.records if record.name == "pitwall.tool.regulation"]
    assert payloads[0]["event"] == "regulation_tool_invoked"
    assert payloads[-1]["event"] == "regulation_tool_completed"
