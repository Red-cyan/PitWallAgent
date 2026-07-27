import logging
import time
from typing import Any, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.config.settings import settings
from app.core.logging import log_structured
from app.core.metrics import LLM_CALLS, LLM_DURATION


class LLMClient:
    def __init__(self, model: str | None = None) -> None:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required for chat generation.")

        self.model = model or settings.llm_model
        self.logger = logging.getLogger("pitwall.llm")
        self.client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        log_structured(
            self.logger,
            "llm_request_started",
            model=self.model,
            message_count=len(messages),
            temperature=temperature,
        )
        started_at = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=cast(list[ChatCompletionMessageParam], messages),
                temperature=temperature,
                max_tokens=max_tokens if max_tokens is not None else settings.llm_max_tokens,
                timeout=timeout,
            )
        except Exception as exc:
            LLM_CALLS.labels(self.model, "error").inc()
            LLM_DURATION.labels(self.model).observe(time.perf_counter() - started_at)
            log_structured(
                self.logger,
                "llm_request_failed",
                model=self.model,
                message_count=len(messages),
                error_type=exc.__class__.__name__,
            )
            raise

        content = response.choices[0].message.content or ""
        LLM_CALLS.labels(self.model, "success").inc()
        LLM_DURATION.labels(self.model).observe(time.perf_counter() - started_at)
        log_structured(
            self.logger,
            "llm_request_completed",
            model=self.model,
            message_count=len(messages),
            output_length=len(content),
        )
        return content
