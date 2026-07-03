from app.repositories.rule_repository import RuleRepository


def test_plank_question_prefers_technical_section() -> None:
    repository = RuleRepository()

    chunks = repository.search_relevant_chunks("What is the plank wear limit?")

    assert chunks
    assert "Section C" in chunks[0].document_title
    assert chunks[0].score is not None


def test_unsafe_release_question_prefers_sporting_section() -> None:
    repository = RuleRepository()

    chunks = repository.search_relevant_chunks("What is an unsafe release?")

    assert chunks
    assert "Section B" in chunks[0].document_title
    assert chunks[0].score is not None


def test_general_principles_question_prefers_general_section() -> None:
    repository = RuleRepository()

    chunks = repository.search_relevant_chunks("What are the general principles?")

    assert chunks
    assert "Section A" in chunks[0].document_title
    assert chunks[0].score is not None


def test_red_flag_question_in_chinese_prefers_sporting_section() -> None:
    class StubQueryRewriter:
        def rewrite(self, question: str) -> list[str]:
            return ["What is a red flag in Formula 1 regulations?"]

    repository = RuleRepository(query_rewriter=StubQueryRewriter())

    chunks = repository.search_relevant_chunks("红旗是什么？")

    assert chunks
    assert "Section B" in chunks[0].document_title
    assert chunks[0].score is not None


def test_red_flag_question_in_chinese_without_rewrite_still_prefers_sporting_section() -> None:
    class EmptyQueryRewriter:
        def rewrite(self, question: str) -> list[str]:
            return []

    repository = RuleRepository(query_rewriter=EmptyQueryRewriter())

    chunks = repository.search_relevant_chunks("\u7ea2\u65d7\u662f\u4ec0\u4e48\uff1f")

    assert chunks
    assert "Section B" in chunks[0].document_title


def test_chinese_pit_lane_speeding_question_expands_to_regulation_keywords() -> None:
    repository = RuleRepository()

    normalized = repository._normalize_question("维修区超速是什么")
    keywords = repository._expand_keywords(normalized)
    preferred_sections = repository._match_preferred_sections(normalized)

    assert "pit" in keywords
    assert "lane" in keywords
    assert "speed" in keywords
    assert "penalty" in keywords
    assert preferred_sections == ["Section B"]


def test_chinese_dangerous_driving_question_expands_to_regulation_keywords() -> None:
    repository = RuleRepository()

    normalized = repository._normalize_question("危险驾驶是什么")
    keywords = repository._expand_keywords(normalized)
    preferred_sections = repository._match_preferred_sections(normalized)

    assert "dangerous" in keywords
    assert "stewards" in keywords
    assert "penalty" in keywords
    assert preferred_sections == ["Section B"]
