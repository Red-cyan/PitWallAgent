from app.rag.retrieval.query_rewriter import QueryRewriter


class StubLLMClient:
    def __init__(self) -> None:
        self.max_tokens: int | None = None
        self.timeout: float | None = None

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        self.max_tokens = max_tokens
        self.timeout = timeout
        return '{"queries":["pit lane speed limit penalty"]}'


class FailingLLMClient:
    def chat(
        self,
        messages: list[dict],
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        raise RuntimeError("llm unavailable")


def test_query_rewriter_uses_short_llm_budget_for_chinese_questions() -> None:
    llm_client = StubLLMClient()
    rewriter = QueryRewriter(llm_client=llm_client)

    queries = rewriter.rewrite("维修区超速是什么")

    assert queries[0] == "pit lane speed limit penalty"
    assert any("FIA Formula 1 regulations" in query for query in queries)
    assert llm_client.max_tokens == 180
    assert llm_client.timeout == 4.0


def test_query_rewriter_skips_non_cjk_questions() -> None:
    llm_client = StubLLMClient()
    rewriter = QueryRewriter(llm_client=llm_client)

    assert rewriter.rewrite("What is parc ferme?") == []
    assert llm_client.max_tokens is None


def test_query_rewriter_returns_structural_fallback_when_llm_fails() -> None:
    rewriter = QueryRewriter(llm_client=FailingLLMClient())

    queries = rewriter.rewrite("\u963b\u6321\u5176\u4ed6\u8f66\u624b\u4f1a\u600e\u6837")

    assert queries
    assert any("Sporting Regulations" in query for query in queries)
