from app.schemas.strategy import StrategyAnalysisRequest
from app.services.strategy import StrategyAnalysisService


class StubLLMClient:
    def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        return (
            '{"recommendation":"Pit under the Safety Car window.","confidence":"medium",'
            '"facts":["The stop loss is reduced under Safety Car"],'
            '"analysis":["Track position can be protected if traffic is manageable"],'
            '"assumptions":["Tyre wear is approaching the crossover point"],'
            '"cautions":["Traffic can erase the gain"]}'
        )


class FailingLLMClient:
    def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        raise RuntimeError("boom")


class StubRaceService:
    def get_next_race(self):
        class Race:
            def model_dump(self, mode: str = "json"):
                return {"grand_prix_name": "British Grand Prix"}

        return Race()

    def get_previous_race(self):
        class Race:
            def model_dump(self, mode: str = "json"):
                return {"grand_prix_name": "Austrian Grand Prix"}

        return Race()


class StubNewsService:
    def list_recent_articles(self, limit: int = 3):
        class Article:
            title = "Ferrari studies undercut risk"
            summary = "Tyre delta remains the deciding factor."

        return [Article()]


class StubKnowledgeService:
    def retrieve_regulation_chunks(self, question: str, top_k: int = 3):
        from app.schemas.rules import RetrievedChunk

        return [
            RetrievedChunk(
                chunk_id="chunk-1",
                content="The Safety Car may be deployed to neutralise a race.",
                score=10.0,
                document_title="FIA 2026 F1 Regulations - Section B [Sporting]",
                article="ARTICLE 55",
                section="Section B",
                page=41,
            )
        ]


def test_strategy_service_returns_llm_analysis() -> None:
    service = StrategyAnalysisService(llm_client=StubLLMClient())

    response = service.analyze(
        StrategyAnalysisRequest(
            question="Should Ferrari pit under safety car?",
            race_context={"tyre_age": 18, "track_position": 5},
            regulation_context=["Safety car delta applies."],
        )
    )

    assert response.recommendation == "Pit under the Safety Car window."
    assert response.confidence == "medium"
    assert response.analysis[0] == "Track position can be protected if traffic is manageable"


def test_strategy_service_falls_back_when_llm_fails() -> None:
    service = StrategyAnalysisService(llm_client=FailingLLMClient())

    response = service.analyze(
        StrategyAnalysisRequest(
            question="Should Ferrari pit under safety car?",
            race_context={"tyre_age": 18},
        )
    )

    assert response.confidence == "low"
    assert "pit" in response.recommendation.lower()


def test_strategy_service_auto_enriches_context_before_llm_call() -> None:
    captured_messages: dict[str, list[dict]] = {}

    class CapturingLLMClient:
        def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
            captured_messages["messages"] = messages
            return (
                '{"recommendation":"Box if the delta is favourable.","confidence":"medium",'
                '"facts":["Safety Car reduces pit loss"],'
                '"analysis":["Track position can be protected"],'
                '"assumptions":["Tyres are near the crossover point"],'
                '"cautions":["Traffic may offset the gain"]}'
            )

    service = StrategyAnalysisService(
        llm_client=CapturingLLMClient(),
        race_service=StubRaceService(),
        news_service=StubNewsService(),
        knowledge_service=StubKnowledgeService(),
    )

    response = service.analyze(StrategyAnalysisRequest(question="Should Ferrari pit under safety car?"))

    payload = captured_messages["messages"][1]["content"]
    assert "British Grand Prix" in payload
    assert "ARTICLE 55" in payload
    assert "Ferrari studies undercut risk" in payload
    assert response.confidence == "medium"
