from fastapi.testclient import TestClient

from serviceflow.main import create_app


def test_health_reports_honestly() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/platform/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    # Nothing unbuilt may claim to be ok (docs/05 principle).
    assert body["checks"]["database"] == "not_configured"
    assert body["checks"]["backup"] == "not_configured"
    assert body["checks"]["license"] == "not_configured"
    assert "X-Request-ID" in resp.headers


def test_error_contract_shape() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/platform/health/nonexistent")
    assert resp.status_code == 404
