from __future__ import annotations

import pytest

from app.services.llm.judge import (
    AnswerVerdict,
    LLMJudge,
    LLMJudgeParseError,
)


class SequenceLLMClient:
    """Yields canned responses in order, then repeats the last one."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float | None = None,
        response_format: dict | None = None,
    ) -> str:
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[index]


def test_judge_parses_valid_json() -> None:
    client = SequenceLLMClient(
        [
            '{"groundedness_score": 5, "helpfulness_score": 4, "rejection_correct": true, '
            '"violations": [], "reasoning": "答案全部有依据。"}'
        ]
    )

    verdict = LLMJudge(llm_client=client).judge("question", "answer", ["evidence"])

    assert verdict.groundedness_score == 5
    assert verdict.helpfulness_score == 4
    assert verdict.rejection_correct is True
    assert verdict.violations == []
    assert client.calls == 1


def test_judge_strips_markdown_fences() -> None:
    client = SequenceLLMClient(
        [
            '```json\n{"groundedness_score": 3, "helpfulness_score": 2, "rejection_correct": false, '
            '"violations": ["编造了积分规则"], "reasoning": "存在无依据内容"}\n```'
        ]
    )

    verdict = LLMJudge(llm_client=client).judge("question", "answer", ["evidence"])

    assert verdict.groundedness_score == 3
    assert verdict.violations == ["编造了积分规则"]


def test_judge_retries_on_malformed_first_response() -> None:
    client = SequenceLLMClient(
        [
            "当然，我来分析一下这个回答。",
            '{"groundedness_score": 4, "helpfulness_score": 4, "rejection_correct": true, '
            '"violations": [], "reasoning": "ok"}',
        ]
    )

    verdict = LLMJudge(llm_client=client).judge("question", "answer", ["evidence"])

    assert verdict.groundedness_score == 4
    assert client.calls == 2


def test_judge_raises_after_repeated_invalid_responses() -> None:
    client = SequenceLLMClient(["not json at all", "still not json", "nope"])

    with pytest.raises(LLMJudgeParseError):
        LLMJudge(llm_client=client).judge("question", "answer", ["evidence"])


def test_answer_verdict_validates_score_range() -> None:
    with pytest.raises(ValueError):
        AnswerVerdict.model_validate(
            {
                "groundedness_score": 9,
                "helpfulness_score": 4,
                "rejection_correct": True,
                "violations": [],
                "reasoning": "",
            }
        )
