from __future__ import annotations

import logging
from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import log_structured


class AccessLogMiddleware(BaseHTTPMiddleware):
    """记录 HTTP 访问日志。"""

    def __init__(self, app) -> None:
        super().__init__(app)
        self.logger = logging.getLogger("pitwall.access")

    async def dispatch(self, request: Request, call_next):
        start_time = perf_counter()
        request_id = getattr(request.state, "request_id", None)

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((perf_counter() - start_time) * 1000, 2)
            log_structured(
                self.logger,
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
                request_id=request_id,
                error_type=exc.__class__.__name__,
            )
            raise

        duration_ms = round((perf_counter() - start_time) * 1000, 2)
        log_structured(
            self.logger,
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return response
