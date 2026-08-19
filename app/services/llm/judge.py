"""LLM-as-judge for end-to-end answer quality evaluation.

The judge scores a generated RAG answer on groundedness (faithfulness to the
retrieved evidence), helpfulness, and whether the answer's decision to answer
or refuse was appropriate. Scores are produced as strict JSON, validated with
Pydantic, and re-parsed once on failure so a malformed LLM reply does not
silently drop a verdict.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.core.logging import log_structured
from app.services.llm.client import LLMClient


class AnswerVerdict(BaseModel):
    """Structured judge output for one question-answer pair."""

    groundedness_score: int = Field(ge=1, le=5, description="How much of the answer is supported by the evidence (1-5).")
    helpfulness_score: int = Field(ge=1, le=5, description="How well the answer addresses the user's question (1-5).")
    rejection_correct: bool = Field(description="Whether answering or refusing was the appropriate choice given the evidence.")
    violations: list[str] = Field(
        default_factory=list,
        description="Concrete claims in the answer that are NOT supported by the evidence.",
    )
    reasoning: str = Field(default="", description="Short justification for the scores.")


class LLMJudgeParseError(Exception):
    """Raised when the judge output cannot be parsed as a valid verdict."""


JUDGE_SYSTEM_PROMPT = (
    "你是一名严格的 AI 问答评测员，负责评测一个基于 FIA F1 规则库的检索增强问答系统。"
    "你会拿到：用户问题、系统回答、以及回答所依据的检索证据片段。"
    "\n\n"
    "评分标准：\n"
    "1. groundedness_score（忠实度，1-5）：回答中的每一条事实陈述是否都能在证据片段中找到依据。"
    "5=全部有依据；4=仅有措辞差异；3=存在少量证据无法支撑的细节；2=一半内容靠编造；1=严重捏造。"
    "如果系统因为证据不足而明确拒绝回答，且没有编造任何内容，忠实度应给高分（4-5）。\n"
    "2. helpfulness_score（有用性，1-5）：回答在多大程度上解决了用户的问题。"
    "拒绝回答时，判断拒绝是否合理且给出了可操作的下一步。\n"
    "3. rejection_correct（回答或拒绝的决策是否正确），按以下规则逐条判断：\n"
    "   - 有证据且回答给出了基于证据的内容 → true；\n"
    "   - 无证据且回答明确拒绝 → true；\n"
    "   - 有证据却回答「证据不足无法回答」→ false；\n"
    "   - 无证据却给出确定答案 → false；\n"
    "   - 证据较弱时的保守 partial 回答，只要未编造并说明了证据局限 → true。\n"
    "4. violations：列出回答中证据无法支持的具体陈述；如果全部有依据则为空列表。\n"
    "\n"
    "只输出一个 JSON 对象，不要输出 markdown 代码块或其他文字，格式如下：\n"
    '{"groundedness_score": 5, "helpfulness_score": 4, "rejection_correct": true, '
    '"violations": ["具体陈述1", "具体陈述2"], "reasoning": "一句话理由"}'
)


class LLMJudge:
    """Judge RAG answers with an LLM, returning a structured AnswerVerdict."""

    def __init__(self, llm_client: LLMClient | None = None, max_tokens: int = 900) -> None:
        self.logger = logging.getLogger("pitwall.eval.judge")
        self.llm_client = llm_client or LLMClient()
        self.max_tokens = max_tokens

    def judge(
        self,
        question: str,
        answer: str,
        evidence_texts: list[str],
        expected_answer_status: str = "answered",
    ) -> AnswerVerdict:
        """Judge one answer against its evidence.

        Args:
            question: the user question.
            answer: the generated answer text.
            evidence_texts: retrieved chunk contents the answer was based on.
            expected_answer_status: the status the system claims
                (answered / partial_evidence / insufficient_evidence), used to
                give the judge context about the intended behavior.
        """
        messages = self._build_messages(question, answer, evidence_texts, expected_answer_status)
        log_structured(
            self.logger,
            "judge_request_started",
            question_length=len(question),
            answer_length=len(answer),
            evidence_count=len(evidence_texts),
        )
        parse_failures = 0
        for attempt in range(6):
            # First two attempts require strict JSON. After an empty or malformed
            # response, fall back to plain text generation with a retry hint so a
            # transient formatting issue does not discard the whole verdict.
            use_json_response_format = attempt < 2
            raw = self.llm_client.chat(
                messages=messages,
                temperature=0 if use_json_response_format else 0.2,
                max_tokens=self.max_tokens,
                response_format=(
                    {"type": "json_object"} if use_json_response_format else None
                ),
            )
            if not raw.strip():
                log_structured(self.logger, "judge_empty_response", attempt=attempt)
                messages = self._with_fix_instruction(messages, raw)
                continue
            try:
                verdict = self._parse(raw)
                log_structured(
                    self.logger,
                    "judge_completed",
                    attempt=attempt,
                    groundedness=verdict.groundedness_score,
                    helpfulness=verdict.helpfulness_score,
                    rejection_correct=verdict.rejection_correct,
                )
                return verdict
            except (json.JSONDecodeError, ValidationError, LLMJudgeParseError) as exc:
                parse_failures += 1
                log_structured(
                    self.logger,
                    "judge_parse_failed",
                    attempt=attempt,
                    error_type=exc.__class__.__name__,
                    raw_preview=raw[:200],
                )
                if parse_failures >= 3:
                    raise LLMJudgeParseError(
                        f"Judge returned invalid JSON 3 times. Last raw output: {raw[:200]!r}"
                    ) from exc
                messages = self._with_fix_instruction(messages, raw)
        raise LLMJudgeParseError("Judge produced no valid verdict after retries.")

    @staticmethod
    def _with_fix_instruction(messages: list[dict[str, Any]], raw: str) -> list[dict[str, Any]]:
        return [
            *messages,
            {"role": "assistant", "content": raw or "(empty)"},
            {
                "role": "user",
                "content": (
                    "你刚才的输出不是一个合法 JSON 对象。"
                    "请只输出符合以下字段的 JSON："
                    '"groundedness_score"(1-5 整数)、"helpfulness_score"(1-5 整数)、'
                    '"rejection_correct"(布尔)、"violations"(字符串数组)、"reasoning"(字符串)。'
                    "不要输出 markdown 代码块。"
                ),
            },
        ]

    def _build_messages(
        self,
        question: str,
        answer: str,
        evidence_texts: list[str],
        expected_answer_status: str,
    ) -> list[dict[str, Any]]:
        evidence_block = "\n\n".join(
            f"[证据 {index}]\n{text}"
            for index, text in enumerate(evidence_texts[:6], start=1)
        )
        user_content = (
            f"用户问题：\n{question}\n\n"
            f"系统回答（声明状态：{expected_answer_status}）：\n{answer}\n\n"
            f"检索到的证据片段：\n{evidence_block if evidence_block else '（无证据）'}"
        )
        return [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        """Extract the first balanced JSON object from model output.

        Scanning brace depth (instead of a greedy regex) avoids pulling
        trailing prose into the payload when the model appends explanations.
        """
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None

    @staticmethod
    def _parse(raw: str) -> AnswerVerdict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE).strip()
        payload_text = LLMJudge._extract_json_object(cleaned)
        if payload_text is None:
            raise LLMJudgeParseError("No JSON object found in judge output.")
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            repaired = re.sub(r",\s*([}\]])", r"\1", payload_text)
            payload = json.loads(repaired)
        return AnswerVerdict.model_validate(payload)
