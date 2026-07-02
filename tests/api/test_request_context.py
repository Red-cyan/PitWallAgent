from fastapi.testclient import TestClient

from app.core.request_context import get_request_id
from app.main import app


@app.get("/__test/request-id")
def read_request_id() -> dict[str, str | None]:
    return {"request_id": get_request_id()}


def test_request_context_generates_request_id_header() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-Id"]


def test_request_context_uses_incoming_request_id() -> None:
    client = TestClient(app)

    response = client.get(
        "/__test/request-id",
        headers={"X-Request-Id": "req-123"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "req-123"
    assert response.json()["request_id"] == "req-123"
