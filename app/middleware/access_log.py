from __future__ import annotations

import logging
from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import log_structured
from app.core.metrics import HTTP_DURATION, HTTP_REQUESTS


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
            duration_seconds = perf_counter() - start_time
            duration_ms = round(duration_seconds * 1000, 2)
            route = self._route_label(request)
            HTTP_REQUESTS.labels(request.method, route, "500").inc()
            HTTP_DURATION.labels(request.method, route).observe(duration_seconds)
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

        duration_seconds = perf_counter() - start_time
        duration_ms = round(duration_seconds * 1000, 2)
        route = self._route_label(request)
        HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        HTTP_DURATION.labels(request.method, route).observe(duration_seconds)
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

    def _route_label(self, request: Request) -> str:
        route = request.scope.get("route")
        return str(getattr(route, "path", request.url.path))
