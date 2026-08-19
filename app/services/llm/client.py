import logging
import threading
import time
from collections.abc import Iterator
from typing import Any, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage, ChatCompletionMessageParam

from app.config.settings import settings
from app.core.logging import log_structured
from app.core.metrics import LLM_CALLS, LLM_DURATION


class LLMCircuitOpenError(RuntimeError):
    """LLM 熔断器打开时的快速失败信号，调用方直接走降级路径。"""


class LLMClient:
    """OpenAI 兼容客户端，带连接复用与熔断保护。

    - 底层 OpenAI client 按 (api_key, base_url) 进程内复用，避免每次调用新建连接。
    - 连续失败达到阈值后熔断打开，后续调用立即抛 LLMCircuitOpenError，
      让上层迅速走降级，而不是在 LLM 故障时串行等待多个超时（可累计 40s+）。
    """

    _client_cache: dict[tuple[str, str], OpenAI] = {}
    _client_lock = threading.Lock()
    _circuit_lock = threading.Lock()
    _consecutive_failures = 0
    _opened_until = 0.0

    def __init__(self, model: str | None = None) -> None:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required for chat generation.")

        self.model = model or settings.llm_model
        self.logger = logging.getLogger("pitwall.llm")
        self.client = self._get_client()

    @classmethod
    def _get_client(cls) -> OpenAI:
        key = (settings.llm_api_key or "", settings.llm_base_url)
        with cls._client_lock:
            client = cls._client_cache.get(key)
            if client is None:
                client = OpenAI(
                    api_key=key[0],
                    base_url=key[1],
                    timeout=settings.llm_timeout_seconds,
                    max_retries=settings.llm_max_retries,
                )
                cls._client_cache[key] = client
            return client

    @classmethod
    def _check_circuit(cls) -> None:
        with cls._circuit_lock:
            if time.monotonic() < cls._opened_until:
                raise LLMCircuitOpenError("LLM circuit breaker is open.")

    @classmethod
    def _record_success(cls) -> None:
        with cls._circuit_lock:
            cls._consecutive_failures = 0

    @classmethod
    def _record_failure(cls) -> None:
        with cls._circuit_lock:
            cls._consecutive_failures += 1
            threshold = settings.llm_circuit_breaker_threshold
            if threshold > 0 and cls._consecutive_failures >= threshold:
                cooldown = max(settings.llm_circuit_breaker_cooldown_seconds, 1.0)
                cls._opened_until = time.monotonic() + cooldown
                cls._consecutive_failures = 0

    def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float | None = None,
        response_format: Any | None = None,
    ) -> str:
        self._check_circuit()
        log_structured(
            self.logger,
            "llm_request_started",
            model=self.model,
            message_count=len(messages),
            temperature=temperature,
        )
        started_at = time.perf_counter()
        try:
            create_kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": cast(list[ChatCompletionMessageParam], messages),
                "temperature": temperature,
                "max_tokens": max_tokens if max_tokens is not None else settings.llm_max_tokens,
                "timeout": timeout,
            }
            if response_format is not None:
                create_kwargs["response_format"] = response_format
            response = self.client.chat.completions.create(**create_kwargs)
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
            self._record_failure()
            raise

        self._record_success()
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

    def chat_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> ChatCompletionMessage:
        """原生 function calling：LLM 可能返回 content 和/或 tool_calls。"""
        self._check_circuit()
        log_structured(
            self.logger,
            "llm_tools_request_started",
            model=self.model,
            message_count=len(messages),
            tool_count=len(tools),
        )
        started_at = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=cast(list[ChatCompletionMessageParam], messages),
                tools=cast(list[Any], tools),
                tool_choice="auto",
                temperature=temperature,
                max_tokens=max_tokens if max_tokens is not None else settings.llm_max_tokens,
                timeout=timeout,
            )
        except Exception as exc:
            LLM_CALLS.labels(self.model, "tools_error").inc()
            LLM_DURATION.labels(self.model).observe(time.perf_counter() - started_at)
            log_structured(
                self.logger,
                "llm_tools_request_failed",
                model=self.model,
                message_count=len(messages),
                error_type=exc.__class__.__name__,
            )
            self._record_failure()
            raise

        self._record_success()
        message = response.choices[0].message
        LLM_CALLS.labels(self.model, "tools_success").inc()
        LLM_DURATION.labels(self.model).observe(time.perf_counter() - started_at)
        log_structured(
            self.logger,
            "llm_tools_request_completed",
            model=self.model,
            message_count=len(messages),
            tool_calls=len(message.tool_calls or []),
        )
        return message

    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> Iterator[str]:
        self._check_circuit()
        log_structured(
            self.logger,
            "llm_stream_started",
            model=self.model,
            message_count=len(messages),
            temperature=temperature,
        )
        started_at = time.perf_counter()
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=cast(list[ChatCompletionMessageParam], messages),
                temperature=temperature,
                max_tokens=max_tokens if max_tokens is not None else settings.llm_max_tokens,
                timeout=timeout,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as exc:
            LLM_CALLS.labels(self.model, "stream_error").inc()
            LLM_DURATION.labels(self.model).observe(time.perf_counter() - started_at)
            log_structured(
                self.logger,
                "llm_stream_failed",
                model=self.model,
                message_count=len(messages),
                error_type=exc.__class__.__name__,
            )
            self._record_failure()
            raise

        self._record_success()
        LLM_CALLS.labels(self.model, "stream_success").inc()
        LLM_DURATION.labels(self.model).observe(time.perf_counter() - started_at)
        log_structured(
            self.logger,
            "llm_stream_completed",
            model=self.model,
            message_count=len(messages),
        )
