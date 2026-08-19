"""CORS for a separately-hosted frontend (e.g. Render) — serviceflow/main.py's
create_app(). Local dev needs none of this: Vite's own proxy makes every
request same-origin from the browser's perspective. Settings.cors_allow_origins
(SERVICEFLOW_CORS_ALLOW_ORIGINS) is the only thing that turns it on; empty by
default. Uses the same no-DB-needed pattern as test_health.py — CORSMiddleware
wraps the whole app before any router/DB access, so a real database is never
required to exercise it."""

from fastapi.testclient import TestClient

from serviceflow.config import Settings
from serviceflow.main import create_app

HEALTH_PATH = "/api/v1/platform/health"


def test_no_cors_headers_when_origins_unset() -> None:
    """The default (local dev) shape: no Settings override needed, no
    Access-Control-* headers on an ordinary same-origin-style request —
    CORSMiddleware is never even added to the stack."""
    client = TestClient(create_app(Settings(_env_file=None, cors_allow_origins="")))
    resp = client.get(HEALTH_PATH, headers={"Origin": "https://serviceflow-frontend.onrender.com"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


def test_allows_exactly_the_configured_frontend_origin() -> None:
    settings = Settings(
        _env_file=None, cors_allow_origins="https://serviceflow-frontend.onrender.com",
    )
    client = TestClient(create_app(settings))
    resp = client.get(HEALTH_PATH, headers={"Origin": "https://serviceflow-frontend.onrender.com"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://serviceflow-frontend.onrender.com"
    assert resp.headers["access-control-allow-credentials"] == "true"


def test_rejects_an_unlisted_origin() -> None:
    """A request from any other origin gets no Access-Control-Allow-Origin
    (or one that doesn't match) — the browser enforces the actual block, but
    the header is the server-side half of that guarantee."""
    settings = Settings(
        _env_file=None, cors_allow_origins="https://serviceflow-frontend.onrender.com",
    )
    client = TestClient(create_app(settings))
    resp = client.get(HEALTH_PATH, headers={"Origin": "https://evil.example.com"})
    assert resp.status_code == 200  # request itself still executes server-side
    assert "access-control-allow-origin" not in resp.headers


def test_preflight_allows_csrf_header_and_mutating_methods() -> None:
    """The exact preflight a real cross-origin POST/PATCH with X-CSRF-Token
    would trigger."""
    settings = Settings(
        _env_file=None, cors_allow_origins="https://serviceflow-frontend.onrender.com",
    )
    client = TestClient(create_app(settings))
    resp = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://serviceflow-frontend.onrender.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://serviceflow-frontend.onrender.com"
    assert resp.headers["access-control-allow-credentials"] == "true"
    allowed_headers = resp.headers["access-control-allow-headers"].lower()
    assert "x-csrf-token" in allowed_headers
    assert "content-type" in allowed_headers
    assert "POST" in resp.headers["access-control-allow-methods"]


def test_supports_multiple_comma_separated_origins() -> None:
    settings = Settings(
        _env_file=None,
        cors_allow_origins="https://serviceflow-frontend.onrender.com, https://staging.example.com",
    )
    client = TestClient(create_app(settings))
    for origin in ("https://serviceflow-frontend.onrender.com", "https://staging.example.com"):
        resp = client.get(HEALTH_PATH, headers={"Origin": origin})
        assert resp.headers["access-control-allow-origin"] == origin
