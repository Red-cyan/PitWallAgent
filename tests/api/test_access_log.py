import json
import logging

from fastapi.testclient import TestClient

from app.main import app


@app.get("/__test/error")
def raise_test_error() -> None:
    raise RuntimeError("boom")


def test_access_log_records_successful_request(caplog) -> None:
    client = TestClient(app)

    with caplog.at_level(logging.INFO, logger="pitwall.access"):
        response = client.get("/health", headers={"X-Request-Id": "req-success"})

    assert response.status_code == 200
    record = next(record for record in caplog.records if record.name == "pitwall.access")
    payload = json.loads(record.message)
    assert payload["event"] == "http_request"
    assert payload["request_id"] == "req-success"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200


def test_access_log_records_failed_request(caplog) -> None:
    transport = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.INFO, logger="pitwall.access"):
        response = transport.get("/__test/error", headers={"X-Request-Id": "req-fail"})

    assert response.status_code == 500
    record = next(record for record in caplog.records if record.name == "pitwall.access")
    payload = json.loads(record.message)
    assert payload["event"] == "http_request"
    assert payload["request_id"] == "req-fail"
    assert payload["path"] == "/__test/error"
    assert payload["status_code"] == 500
    assert payload["error_type"] == "RuntimeError"
