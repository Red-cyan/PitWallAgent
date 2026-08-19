"""Last-good cache for upstream data.

When a live upstream (Jolpica / RSS) is unavailable, the system degrades to the
most recent successfully fetched data instead of fabricated sample data. This
module provides a small Redis-backed store for that purpose. When Redis is not
available the cache is a no-op, so callers always keep the original fallback.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

from app.config.settings import settings


class DataCache:
    """Redis-backed last-good store with graceful no-op when Redis is down."""

    KEY_PREFIX = "last_good:"

    def __init__(
        self,
        client: Any | None = None,
        enabled: bool | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        self.logger = logging.getLogger("pitwall.data_cache")
        self.enabled = settings.data_cache_enabled if enabled is None else enabled
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.data_cache_ttl_seconds
        self._client = client
        self._resolved = client is not None

    @property
    def available(self) -> bool:
        if not self.enabled:
            return False
        # TTL<=0 表示禁用缓存（语义明确的"不缓存"），而不是永不过期。
        if self.ttl_seconds is not None and self.ttl_seconds <= 0:
            return False
        if not self._resolved:
            self._client = self._build_client()
            self._resolved = True
        return self._client is not None

    def get_last_good(self, key: str) -> dict[str, Any] | None:
        if not self.available:
            return None
        client = cast(Any, self._client)
        try:
            raw = client.get(f"{self.KEY_PREFIX}{key}")
        except Exception:
            return None
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def set_last_good(
        self,
        key: str,
        value: list[dict[str, Any]] | dict[str, Any],
        fetched_at: str | None = None,
    ) -> None:
        if not self.available:
            return
        client = cast(Any, self._client)
        try:
            payload = {
                "fetched_at": fetched_at or datetime.now(UTC).isoformat(),
                "data": value,
            }
            client.set(
                f"{self.KEY_PREFIX}{key}",
                json.dumps(payload, ensure_ascii=False),
                ex=max(int(self.ttl_seconds), 1),
            )
        except Exception:
            self.logger.debug("data_cache_set_failed", exc_info=True)

    def _build_client(self) -> Any | None:
        try:
            from redis import Redis

            client = Redis.from_url(
                settings.resolved_redis_url,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            client.ping()
            return client
        except Exception:
            return None
