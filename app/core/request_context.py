from __future__ import annotations

from contextvars import ContextVar


_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str) -> None:
    """设置当前请求 ID。"""

    _request_id_var.set(request_id)


def get_request_id() -> str | None:
    """读取当前请求 ID。"""

    return _request_id_var.get()


def clear_request_id() -> None:
    """清理当前请求 ID。"""

    _request_id_var.set(None)
