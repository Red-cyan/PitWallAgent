from __future__ import annotations

import hmac
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config.settings import settings

# 放行的路径：健康检查与 Prometheus 指标保持匿名可访问。
_PUBLIC_PATHS = {"/", "/health", "/health/live", "/health/ready", "/metrics"}


class ApiAuthMiddleware(BaseHTTPMiddleware):
    """可选 Bearer token 认证中间件。

    当配置了 API_ACCESS_TOKEN 时，除健康检查与指标外的所有请求必须携带
    Authorization: Bearer <token>；否则返回 401。未配置时保持匿名（默认），
    便于本地开发。
    """

    HEADER_NAME = "Authorization"
    SCHEME = "Bearer"

    async def dispatch(self, request: Request, call_next):
        token = settings.api_access_token
        if not token:
            return await call_next(request)

        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        provided = request.headers.get(self.HEADER_NAME, "")
        expected = f"{self.SCHEME} {token}"
        if not secrets.compare_digest(provided, expected) and not hmac.compare_digest(
            provided, expected
        ):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid API token."},
            )
        return await call_next(request)
