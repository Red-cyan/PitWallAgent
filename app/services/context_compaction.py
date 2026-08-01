from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

from app.config.settings import settings
from app.core.logging import log_structured
from app.schemas.chat import ConversationTurn


SUMMARY_KEYS = ("topic", "facts", "preferences", "open_loops", "entities")


class SummaryLLM(Protocol):
    def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        ...


@dataclass
class CompactionResult:
    summary: str
    mode: str
    fallback: bool
    input_tokens: int
    output_tokens: int


class ContextCompactionService:
    """Incrementally compact evicted conversation turns into structured memory."""

    def __init__(self, llm_client: SummaryLLM | None = None) -> None:
        self.llm_client = llm_client
        self.logger = logging.getLogger("pitwall.memory_compaction")

    def compact(
        self,
        existing_summary: str | None,
        turns: list[ConversationTurn],
    ) -> CompactionResult:
        input_text = self._build_input(existing_summary, turns)
        input_tokens = self.estimate_tokens(input_text)
        started_at = time.perf_counter()

        if settings.memory_compression_enabled:
            try:
                client = self._get_llm_client()
                raw = client.chat(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Summarize conversation memory. Return JSON only with exactly these keys: "
                                "topic (string), facts (array of strings), preferences (array of strings), "
                                "open_loops (array of strings), entities (array of strings). "
                                "Preserve confirmed facts, user preferences, unresolved follow-ups, and key entities. "
                                "Do not invent information. Keep the JSON concise."
                            ),
                        },
                        {"role": "user", "content": input_text},
                    ],
                    temperature=0.05,
                    max_tokens=settings.memory_summary_token_budget,
                    timeout=settings.memory_compression_timeout_seconds,
                )
                self._validate_raw_json(raw)
                summary = self.normalize(raw, existing_summary, turns)
                result = CompactionResult(
                    summary=summary,
                    mode="llm",
                    fallback=False,
                    input_tokens=input_tokens,
                    output_tokens=self.estimate_tokens(summary),
                )
                log_structured(
                    self.logger,
                    "memory_compaction_completed",
                    mode=result.mode,
                    fallback=False,
                    input_tokens=input_tokens,
                    input_length=len(input_text),
                    output_tokens=result.output_tokens,
                    output_length=len(summary),
                    duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                )
                return result
            except Exception as exc:
                log_structured(
                    self.logger,
                    "memory_compaction_failed",
                    error_type=exc.__class__.__name__,
                    fallback_reason="llm_error_or_invalid_json",
                    input_tokens=input_tokens,
                    input_length=len(input_text),
                    duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                )

        summary = self.normalize(None, existing_summary, turns)
        result = CompactionResult(
            summary=summary,
            mode="deterministic",
            fallback=settings.memory_compression_enabled,
            input_tokens=input_tokens,
            output_tokens=self.estimate_tokens(summary),
        )
        log_structured(
            self.logger,
            "memory_compaction_completed",
            mode=result.mode,
            fallback=result.fallback,
            input_tokens=input_tokens,
            input_length=len(input_text),
            output_tokens=result.output_tokens,
            output_length=len(summary),
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return result

    def _validate_raw_json(self, raw: str) -> None:
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        try:
            parsed = json.loads(cleaned)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("summary response was not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("summary response was not a JSON object")

    def normalize(
        self,
        raw: str | None,
        existing_summary: str | None,
        turns: list[ConversationTurn],
    ) -> str:
        data: dict[str, Any] = {}
        if raw:
            try:
                parsed = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
                if isinstance(parsed, dict):
                    data = parsed
            except (TypeError, json.JSONDecodeError):
                data = {}

        legacy = self._parse_summary(existing_summary)
        topic = self._string(data.get("topic")) or legacy.get("topic", "")
        normalized: dict[str, Any] = {"topic": topic, "facts": [], "preferences": [], "open_loops": [], "entities": []}
        for key in SUMMARY_KEYS[1:]:
            response_values = data.get(key)
            values = response_values if isinstance(response_values, list) else []
            # Treat the model response as an incremental update: existing memory
            # remains authoritative when a provider omits an item.
            legacy_values = legacy.get(key)
            if not isinstance(legacy_values, list):
                legacy_values = []
            normalized[key] = self._unique_strings([*legacy_values, *values])

        if existing_summary and not self._is_structured(existing_summary):
            normalized["facts"].insert(0, f"Legacy summary: {self._compact_text(existing_summary)}")
        if not raw or not data:
            for turn in turns:
                role = "User" if turn.role == "user" else "Assistant"
                normalized["facts"].append(f"{role}: {self._compact_text(turn.message)}")
        normalized["facts"] = self._unique_strings(normalized["facts"])
        return self._fit(normalized)

    def _get_llm_client(self) -> SummaryLLM:
        if self.llm_client is None:
            from app.services.llm.client import LLMClient

            self.llm_client = LLMClient(model=settings.llm_model)
        return self.llm_client

    def _build_input(self, existing_summary: str | None, turns: list[ConversationTurn]) -> str:
        previous = existing_summary or "(none)"
        messages = "\n".join(
            f"{'User' if turn.role == 'user' else 'Assistant'}: {turn.message}" for turn in turns
        )
        return f"Existing memory:\n{previous}\n\nNewly evicted turns:\n{messages}"

    def _parse_summary(self, summary: str | None) -> dict[str, Any]:
        if not summary:
            return {}
        try:
            value = json.loads(summary)
            if isinstance(value, dict):
                return {key: value.get(key) for key in SUMMARY_KEYS if key in value}
        except json.JSONDecodeError:
            pass
        return {}

    def _is_structured(self, summary: str) -> bool:
        return bool(self._parse_summary(summary))

    def _fit(self, data: dict[str, Any]) -> str:
        budget = max(settings.memory_summary_token_budget, 1)
        for key in ("facts", "preferences", "open_loops", "entities"):
            data[key] = data[key][:40]
        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        while self.estimate_tokens(encoded) > budget and any(data[key] for key in SUMMARY_KEYS[1:]):
            key = max(SUMMARY_KEYS[1:], key=lambda item: len(data[item]))
            if data[key]:
                data[key].pop()
            encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        if self.estimate_tokens(encoded) > budget:
            data["topic"] = self._compact_text(data["topic"])
            encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            while self.estimate_tokens(encoded) > budget and data["topic"]:
                data["topic"] = data["topic"][:-1]
                encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return encoded

    def _unique_strings(self, values: list[Any]) -> list[str]:
        result: list[str] = []
        for value in values:
            text = self._string(value)
            if text and text not in result:
                result.append(text)
        return result

    def _string(self, value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    def _compact_text(self, text: str) -> str:
        normalized = " ".join(text.split())
        return normalized if len(normalized) <= 240 else normalized[:237].rstrip() + "..."

    def estimate_tokens(self, text: str | None) -> int:
        if not text:
            return 0
        ascii_chars = sum(1 for char in text if ord(char) < 128)
        return max(1, (ascii_chars // 4) + len(text) - ascii_chars)
