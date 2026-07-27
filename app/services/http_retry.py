from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx

from app.config.settings import settings
from app.core.logging import log_structured
from app.core.metrics import UPSTREAM_DURATION, UPSTREAM_REQUESTS, UPSTREAM_RETRIES


def get_with_retry(
    url: str,
    *,
    provider: str,
    timeout: float,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
    request: Callable[..., httpx.Response] = httpx.get,
) -> httpx.Response:
    """GET an upstream resource with bounded exponential backoff."""

    logger = logging.getLogger("pitwall.upstream")
    max_retries = max(settings.upstream_get_max_retries, 0)
    started_at = time.perf_counter()
    try:
        for attempt in range(max_retries + 1):
            try:
                response = request(
                    url,
                    timeout=timeout,
                    headers=headers,
                    follow_redirects=follow_redirects,
                )
                response.raise_for_status()
                UPSTREAM_REQUESTS.labels(provider, "success").inc()
                return response
            except httpx.HTTPError as exc:
                retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }
                if attempt >= max_retries or not retryable:
                    UPSTREAM_REQUESTS.labels(provider, "error").inc()
                    log_structured(
                        logger,
                        "upstream_get_failed",
                        provider=provider,
                        attempt=attempt + 1,
                        error_type=exc.__class__.__name__,
                    )
                    raise
                UPSTREAM_RETRIES.labels(provider).inc()
                delay = max(settings.upstream_get_backoff_seconds, 0) * (2**attempt)
                log_structured(
                    logger,
                    "upstream_get_retry",
                    provider=provider,
                    attempt=attempt + 1,
                    delay_seconds=delay,
                    error_type=exc.__class__.__name__,
                )
                if delay:
                    time.sleep(delay)
        raise RuntimeError("unreachable")
    finally:
        UPSTREAM_DURATION.labels(provider).observe(time.perf_counter() - started_at)
