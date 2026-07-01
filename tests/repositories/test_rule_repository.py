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
