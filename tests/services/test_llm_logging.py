import json
import logging

import pytest

from app.services.llm.client import LLMClient


class StubCompletions:
    def __init__(self, content: str = "stub content", should_fail: bool = False) -> None:
        self.content = content
        self.should_fail = should_fail

    def create(self, **kwargs):
        if self.should_fail:
            raise RuntimeError("boom")

        class Message:
            content = self.content

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        return Response()


class StubChat:
    def __init__(self, completions: StubCompletions) -> None:
        self.completions = completions


class StubOpenAIClient:
    def __init__(self, completions: StubCompletions) -> None:
        self.chat = StubChat(completions)


def build_client(completions: StubCompletions) -> LLMClient:
    client = object.__new__(LLMClient)
    client.model = "deepseek-v4-flash"
    client.logger = logging.getLogger("pitwall.llm")
    client.client = StubOpenAIClient(completions)
    return client


def test_llm_client_emits_success_logs(caplog) -> None:
    client = build_client(StubCompletions(content="hello"))

    with caplog.at_level(logging.INFO, logger="pitwall.llm"):
        result = client.chat(messages=[{"role": "user", "content": "hi"}], temperature=0.1)

    assert result == "hello"
    payloads = [json.loads(record.message) for record in caplog.records if record.name == "pitwall.llm"]
    assert payloads[0]["event"] == "llm_request_started"
    assert payloads[-1]["event"] == "llm_request_completed"


def test_llm_client_emits_failure_logs(caplog) -> None:
    client = build_client(StubCompletions(should_fail=True))

    with caplog.at_level(logging.INFO, logger="pitwall.llm"):
        with pytest.raises(RuntimeError):
            client.chat(messages=[{"role": "user", "content": "hi"}], temperature=0.1)

    payloads = [json.loads(record.message) for record in caplog.records if record.name == "pitwall.llm"]
    assert payloads[0]["event"] == "llm_request_started"
    assert payloads[-1]["event"] == "llm_request_failed"
