from fastapi.testclient import TestClient

from app.main import app


def test_liveness_does_not_require_dependencies() -> None:
    response = TestClient(app).get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_503_when_a_dependency_is_degraded(monkeypatch) -> None:
    from app.api import router

    monkeypatch.setattr(
        router,
        "_health_payload",
        lambda: {"status": "degraded", "checks": {"database": {"status": "degraded"}}},
    )
    response = TestClient(app).get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_metrics_exposes_http_counters_with_route_templates() -> None:
    client = TestClient(app)
    client.get("/health/live")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "pitwall_http_requests_total" in response.text
    assert 'route="/health/live"' in response.text
