import httpx
import pytest

from app.services.http_retry import get_with_retry


def _response(status_code: int) -> httpx.Response:
    request = httpx.Request("GET", "https://example.test/data")
    return httpx.Response(status_code, request=request, text="ok")


def test_get_with_retry_retries_transient_failure(monkeypatch) -> None:
    attempts = 0

    def request(*args, **kwargs) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("timeout")
        return _response(200)

    monkeypatch.setattr("app.services.http_retry.settings.upstream_get_backoff_seconds", 0)
    response = get_with_retry(
        "https://example.test/data",
        provider="test",
        timeout=1,
        request=request,
    )

    assert response.status_code == 200
    assert attempts == 2


def test_get_with_retry_does_not_retry_client_error(monkeypatch) -> None:
    attempts = 0

    def request(*args, **kwargs) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return _response(404)

    monkeypatch.setattr("app.services.http_retry.settings.upstream_get_backoff_seconds", 0)
    with pytest.raises(httpx.HTTPStatusError):
        get_with_retry(
            "https://example.test/data",
            provider="test",
            timeout=1,
            request=request,
        )

    assert attempts == 1
