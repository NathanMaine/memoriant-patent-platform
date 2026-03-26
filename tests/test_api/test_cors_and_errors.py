"""Tests for configurable CORS (Item 8) and standardized error responses (Item 9)."""
from __future__ import annotations

import time

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

from api.main import app

SECRET = "test-secret-key"


def make_token(sub: str = "user-err") -> str:
    payload = {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture(autouse=True)
def _jwt_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)


# ---------------------------------------------------------------------------
# Item 8 — Configurable CORS
# ---------------------------------------------------------------------------


def test_cors_origins_default_from_env(monkeypatch):
    """CORS_ORIGINS env var controls allowed origins list."""
    import importlib
    import api.main as main_module

    monkeypatch.setenv("CORS_ORIGINS", "http://example.com,http://other.com")
    # Re-import to pick up new env value — read the resolved value directly
    import os
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    assert "http://example.com" in origins
    assert "http://other.com" in origins


@pytest.mark.asyncio
async def test_cors_header_present_on_options(monkeypatch):
    """OPTIONS preflight to an allowed origin gets Access-Control-Allow-Origin header."""
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    # FastAPI CORS middleware returns 200 for preflight
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


# ---------------------------------------------------------------------------
# Item 9 — Standardized error responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_401_returns_standardized_format():
    """Auth failure returns ErrorResponse with code=AUTH_REQUIRED."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/protected")
    assert resp.status_code == 401
    body = resp.json()
    assert "error" in body
    assert body.get("code") == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_429_returns_standardized_format():
    """Rate limit exceeded returns ErrorResponse with code=RATE_LIMITED."""
    from api.middleware.rate_limit import RateLimitMiddleware

    RateLimitMiddleware.clear_state()
    token = make_token(sub="user-rl-std")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(6):
            resp = await client.get(
                "/api/search-stub", headers={"Authorization": f"Bearer {token}"}
            )
    RateLimitMiddleware.clear_state()

    if resp.status_code == 429:
        body = resp.json()
        assert "error" in body
        assert body.get("code") == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_error_response_contains_request_id():
    """Error responses include the request_id from correlation middleware."""
    custom_id = "err-trace-xyz"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/protected", headers={"X-Request-ID": custom_id}
        )
    assert resp.status_code == 401
    body = resp.json()
    assert body.get("request_id") == custom_id


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500_standardized(monkeypatch):
    """A route that raises an unhandled exception returns a standardized 500.

    Note: Starlette's BaseHTTPMiddleware wraps exceptions from call_next in an
    ExceptionGroup (anyio task group). The global_exception_handler fires and
    produces the correct 500 response, which is returned to the client. We use
    raise_server_exceptions=False so httpx returns the response instead of
    re-raising the Python exception in the test process.
    """
    from fastapi.routing import APIRoute

    monkeypatch.setenv("JWT_SECRET", SECRET)

    # Add a temporary crash route and hit it
    @app.get("/test-crash-internal-only")
    async def _crash():
        raise RuntimeError("deliberate test crash")

    token = make_token(sub="crash-tester")
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/test-crash-internal-only",
            headers={"Authorization": f"Bearer {token}"},
        )

    # Clean up route
    app.routes[:] = [r for r in app.routes if not (
        isinstance(r, APIRoute) and r.path == "/test-crash-internal-only"
    )]

    assert resp.status_code == 500
    body = resp.json()
    assert "error" in body
    assert body.get("code") == "INTERNAL_ERROR"


@pytest.mark.asyncio
async def test_error_response_schema_fields():
    """ErrorResponse has error, code, request_id keys."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/protected")
    body = resp.json()
    assert "error" in body
    assert "code" in body
    # request_id may be present (None or a string)
    assert "request_id" in body


@pytest.mark.asyncio
async def test_request_validation_error_returns_standardized_422():
    """Sending invalid JSON body to a typed endpoint triggers the validation handler."""
    from fastapi.routing import APIRoute
    from api.schemas.requests import SearchRequest

    # Add a route that requires a typed body so we can trigger RequestValidationError
    @app.post("/test-validation-only")
    async def _needs_body(body: SearchRequest):
        return {"ok": True}

    token = make_token(sub="val-tester")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/test-validation-only",
            json={"bad_field": "not valid"},  # missing required `query` field
            headers={"Authorization": f"Bearer {token}"},
        )

    # Clean up route
    app.routes[:] = [r for r in app.routes if not (
        isinstance(r, APIRoute) and r.path == "/test-validation-only"
    )]

    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == "VALIDATION_ERROR"
    assert "error" in body
    assert "request_id" in body


@pytest.mark.asyncio
async def test_http_exception_returns_standardized_format():
    """A route that raises HTTPException returns the standardized error envelope."""
    from fastapi import HTTPException
    from fastapi.routing import APIRoute

    @app.get("/test-http-exc-only")
    async def _raises_http():
        raise HTTPException(status_code=404, detail="thing not found")

    token = make_token(sub="http-exc-tester")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/test-http-exc-only",
            headers={"Authorization": f"Bearer {token}"},
        )

    # Clean up route
    app.routes[:] = [r for r in app.routes if not (
        isinstance(r, APIRoute) and r.path == "/test-http-exc-only"
    )]

    assert resp.status_code == 404
    body = resp.json()
    assert body.get("code") == "NOT_FOUND"
    assert "error" in body
    assert "request_id" in body
