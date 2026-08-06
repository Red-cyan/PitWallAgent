from __future__ import annotations

from datetime import UTC, datetime

import anyio

from app.mcp.pitwall_server import PitWallServer
from app.schemas.news import NewsArticleRead
from app.schemas.race import (
    ConstructorStandingEntry,
    DriverStandingEntry,
    RaceResult,
    RaceResultEntry,
    RaceWeekend,
    SessionInfo,
)
from app.schemas.rules import (
    Citation,
    RetrievedChunk,
    RetrievalDebugResponse,
    RuleAskRequest,
    RuleAskResponse,
)


class StubQAService:
    def __init__(self) -> None:
        self._chunk = RetrievedChunk(
            chunk_id="chunk-unsafe-release",
            content="Unsafe release occurs when a car is released in a way that endangers pit lane personnel.",
            score=12.0,
            document_title="FIA 2026 F1 Regulations - Section B [Sporting] - Iss 07 - 2026-06-25",
            article="(4)",
            page=9,
            score_components={"evidence_strength": 1.0},
        )

    def ask(self, request: RuleAskRequest) -> RuleAskResponse:
        if "外星" in request.question:
            return RuleAskResponse(
                answer="未检索到相关 FIA 规则证据。为了避免编造规则，我不能基于当前资料给出确定答案。",
                answer_status="insufficient_evidence",
                confidence="low",
                evidence_count=0,
                source_mode="regulation_rag",
                query_type="fact_lookup",
            )
        return RuleAskResponse(
            answer="不安全释放指赛车在放行时危及维修区人员或他人的情况。关键依据：Section B，条款 (4)。",
            answer_status="answered",
            confidence="medium",
            evidence_count=1,
            source_mode="regulation_rag",
            query_type="fact_lookup",
            citations=[
                Citation(
                    document_title=self._chunk.document_title,
                    article=self._chunk.article,
                    section=self._chunk.section,
                    page=self._chunk.page,
                    excerpt=self._chunk.content,
                )
            ],
        )

    def debug_retrieval(self, request: RuleAskRequest, top_k: int | None = None) -> RetrievalDebugResponse:
        return RetrievalDebugResponse(
            question=request.question,
            normalized_question=request.question,
            rewritten_queries=[],
            retrieval_queries=[request.question],
            extracted_phrases=["unsafe release"],
            expanded_keywords=["unsafe", "release"],
            preferred_sections=[],
            keyword_candidates=[self._chunk],
            vector_candidates=[self._chunk],
            hybrid_candidates=[self._chunk],
            retrieved_chunks=[self._chunk],
        )


class StubRaceService:
    def __init__(self) -> None:
        self._race = RaceWeekend(
            season=2026,
            round_number=8,
            grand_prix_name="Austrian Grand Prix",
            circuit_name="Red Bull Ring",
            country="Austria",
            start_date=datetime(2026, 6, 26, 11, 30, tzinfo=UTC),
            end_date=datetime(2026, 6, 28, 13, 0, tzinfo=UTC),
            sessions=[SessionInfo(name="Race", start_time=datetime(2026, 6, 28, 13, 0, tzinfo=UTC))],
            source="stub",
        )

    def list_schedule(self, season: str):
        return [self._race]

    def get_next_race(self, season: str):
        return self._race

    def get_previous_race(self, season: str):
        return self._race

    def list_driver_standings(self, season: str) -> list[DriverStandingEntry]:
        return [DriverStandingEntry(position=1, driver_name="Andrea Kimi Antonelli", team_name="Mercedes", points=171, source="stub")]

    def list_constructor_standings(self, season: str) -> list[ConstructorStandingEntry]:
        return [ConstructorStandingEntry(position=1, team_name="Mercedes", points=302, source="stub")]

    def get_race_results(self, season: str, round_number: int | None = None) -> RaceResult:
        return RaceResult(
            season=2026,
            round_number=8,
            grand_prix_name="Austrian Grand Prix",
            results=[
                RaceResultEntry(position=1, driver_name="Andrea Kimi Antonelli", team_name="Mercedes", points=25, source="stub"),
                RaceResultEntry(position=2, driver_name="Charles Leclerc", team_name="Ferrari", points=18, source="stub"),
            ],
            source="stub",
        )


class StubNewsService:
    def __init__(self) -> None:
        self._article = NewsArticleRead(
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

    def list_recent_articles(self, limit: int = 20) -> list[NewsArticleRead]:
        return [self._article][:limit]

    def search_articles(self, query: str, limit: int = 10) -> list[NewsArticleRead]:
        return [self._article][:limit]


def _build_server() -> PitWallServer:
    return PitWallServer(
        qa_service=StubQAService(),
        race_service=StubRaceService(),
        news_service=StubNewsService(),
    )


def test_registers_all_tools() -> None:
    server = _build_server()

    async def _list_tools() -> set[str]:
        tools = await server.app.list_tools()
        return {tool.name for tool in tools}

    names = anyio.run(_list_tools)

    assert names == {
        "regulation_ask",
        "regulation_debug_retrieval",
        "race_schedule",
        "race_next",
        "race_previous",
        "race_driver_standings",
        "race_constructor_standings",
        "race_results",
        "news_search",
        "news_recent",
    }


def test_regulation_ask_returns_grounded_answer() -> None:
    server = _build_server()

    result = server.regulation_ask("什么是不安全释放？")

    assert result["success"] is True
    assert result["answer_status"] == "answered"
    assert result["evidence_count"] == 1
    assert "不安全释放" in result["answer"]
    assert result["citations"][0]["article"] == "(4)"


def test_regulation_ask_refuses_when_insufficient_evidence() -> None:
    server = _build_server()

    result = server.regulation_ask("外星人赛车怎么处理？")

    assert result["success"] is True
    assert result["answer_status"] == "insufficient_evidence"
    assert result["evidence_count"] == 0
    assert "避免编造规则" in result["answer"]


def test_regulation_debug_retrieval_returns_pipeline() -> None:
    server = _build_server()

    result = server.regulation_debug_retrieval("What is an unsafe release?", top_k=5)

    assert result["success"] is True
    assert result["expanded_keywords"] == ["unsafe", "release"]
    assert len(result["keyword_candidates"]) == 1
    assert result["retrieved_chunks"][0]["chunk_id"] == "chunk-unsafe-release"


def test_race_schedule_returns_calendar() -> None:
    server = _build_server()

    result = server.race_schedule()

    assert result["success"] is True
    assert result["races"][0]["grand_prix_name"] == "Austrian Grand Prix"


def test_race_results_returns_finishing_order() -> None:
    server = _build_server()

    result = server.race_results()

    assert result["success"] is True
    assert result["race_result"]["results"][0]["driver_name"] == "Andrea Kimi Antonelli"
    assert result["race_result"]["results"][0]["position"] == 1


def test_race_standings_returned() -> None:
    server = _build_server()

    drivers = server.race_driver_standings()
    constructors = server.race_constructor_standings()

    assert drivers["success"] is True
    assert drivers["standings"][0]["points"] == 171
    assert constructors["standings"][0]["team_name"] == "Mercedes"


def test_news_search_returns_articles() -> None:
    server = _build_server()

    result = server.news_search("McLaren upgrade", limit=5)

    assert result["success"] is True
    assert result["query"] == "McLaren upgrade"
    assert len(result["articles"]) == 1
    assert result["articles"][0]["title"].startswith("Race suspended")


def test_news_search_requires_query() -> None:
    server = _build_server()

    result = server.news_search("   ")

    assert result["success"] is False
    assert result["error"] == "News search requires a query."
