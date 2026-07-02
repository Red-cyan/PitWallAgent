from datetime import UTC, datetime

from app.schemas.news import NewsArticleRead
from app.schemas.rules import RetrievedChunk
from app.services.news_rule_analysis_service import NewsRuleAnalysisService


class StubRuleRepository:
    def search_relevant_chunks(self, question: str, top_k: int = 3) -> list[RetrievedChunk]:
        if "red flag" in question.lower():
            return [
                RetrievedChunk(
                    chunk_id="chunk-red-flag",
                    content="When the race is suspended, red flags will be shown at all marshal posts.",
                    score=14.0,
                    document_title="FIA 2026 F1 Regulations - Section B [Sporting] - Iss 07 - 2026-06-25",
                    article="B5.14.2",
                    page=47,
                )
            ]
        return []


def test_news_rule_analysis_matches_topic_and_returns_related_chunks() -> None:
    service = NewsRuleAnalysisService(rule_repository=StubRuleRepository())
    article = NewsArticleRead(
        id=1,
        source_name="formula1",
        source_article_id="news-001",
        title="Race suspended after heavy rain",
        summary="The red flag was shown after extreme weather.",
        content="Race control suspended the session with a red flag.",
        article_url="https://www.formula1.com/en/latest/article/test-1.123.html",
        author="F1",
        published_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
        tags=["red-flag"],
        fetched_at=datetime(2026, 7, 1, 10, 5, tzinfo=UTC),
        is_deleted=False,
    )

    analysis = service.analyze(article=article, top_k=3)

    assert len(analysis.matched_topics) == 1
    assert analysis.matched_topics[0].topic_key == "red_flag"
    assert analysis.suggested_questions
    assert len(analysis.related_chunks) == 1
    assert "红旗与比赛暂停" in analysis.analysis_summary


def test_news_rule_analysis_falls_back_to_generic_questions() -> None:
    service = NewsRuleAnalysisService(rule_repository=StubRuleRepository())
    article = NewsArticleRead(
        id=2,
        source_name="formula1",
        source_article_id="news-002",
        title="Hamilton attends fan event",
        summary="A lifestyle event was held ahead of the Grand Prix weekend.",
        content=None,
        article_url="https://www.formula1.com/en/latest/article/test-1.456.html",
        author="F1",
        published_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        tags=[],
        fetched_at=datetime(2026, 7, 1, 12, 5, tzinfo=UTC),
        is_deleted=False,
    )

    analysis = service.analyze(article=article, top_k=3)

    assert analysis.matched_topics == []
    assert len(analysis.suggested_questions) == 2
    assert "未命中明确的预设规则主题" in analysis.analysis_summary
