import pytest

from app.services.llm.client import LLMCircuitOpenError, LLMClient


class _FakeCompletions:
    def __init__(self, behavior) -> None:  # noqa: ANN001
        self.behavior = behavior

    def create(self, **kwargs):  # noqa: ANN003
        return self.behavior()


class _FakeChat:
    def __init__(self, behavior) -> None:  # noqa: ANN001
        self.completions = _FakeCompletions(behavior)


class _FakeOpenAIClient:
    def __init__(self, behavior) -> None:  # noqa: ANN001
        self.chat = _FakeChat(behavior)


class _FakeMessage:
    content = "ok"


class _FakeChoice:
    message = _FakeMessage()


class _FakeCompletion:
    choices = [_FakeChoice()]


def test_llm_client_reuses_underlying_openai_client(monkeypatch) -> None:
    monkeypatch.setattr("app.services.llm.client.settings.llm_api_key", "test-key")

    first = LLMClient()
    second = LLMClient()

    assert first.client is second.client


def test_circuit_breaker_opens_after_consecutive_failures(monkeypatch) -> None:
    monkeypatch.setattr("app.services.llm.client.settings.llm_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.llm.client.settings.llm_circuit_breaker_threshold", 2
    )
    monkeypatch.setattr(
        "app.services.llm.client.settings.llm_circuit_breaker_cooldown_seconds", 60
    )

    # 重置熔断状态，避免跨测试污染
    LLMClient._consecutive_failures = 0
    LLMClient._opened_until = 0.0

    def fail() -> None:
        raise RuntimeError("upstream down")

    client = LLMClient()
    client.client = _FakeOpenAIClient(fail)  # type: ignore[assignment]

    with pytest.raises(RuntimeError):
        client.chat(messages=[], temperature=0)
    with pytest.raises(RuntimeError):
        client.chat(messages=[], temperature=0)

    # 第三次调用直接熔断打开，快速失败，不再触碰底层 client
    with pytest.raises(LLMCircuitOpenError):
        client.chat(messages=[], temperature=0)


def test_circuit_breaker_recovers_after_success(monkeypatch) -> None:
    monkeypatch.setattr("app.services.llm.client.settings.llm_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.llm.client.settings.llm_circuit_breaker_threshold", 2
    )

    LLMClient._consecutive_failures = 0
    LLMClient._opened_until = 0.0

    calls = {"count": 0}

    def flaky() -> _FakeCompletion:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient")
        return _FakeCompletion()

    client = LLMClient()
    client.client = _FakeOpenAIClient(flaky)  # type: ignore[assignment]

    with pytest.raises(RuntimeError):
        client.chat(messages=[], temperature=0)

    # 成功调用重置失败计数
    assert client.chat(messages=[], temperature=0) == "ok"
    assert LLMClient._consecutive_failures == 0
