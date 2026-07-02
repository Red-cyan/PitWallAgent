from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.request_context import clear_request_id, set_request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 request_id。"""

    HEADER_NAME = "X-Request-Id"

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(self.HEADER_NAME) or uuid4().hex
        request.state.request_id = request_id
        set_request_id(request_id)

        try:
            response = await call_next(request)
        finally:
            clear_request_id()

        response.headers[self.HEADER_NAME] = request_id
        return response
