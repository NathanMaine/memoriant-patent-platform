"""Tests for request correlation ID middleware (Item 1)."""
from __future__ import annotations

import re
import time

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

from api.main import app

SECRET = "test-secret-key"
UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def make_token(sub: str = "user-corr") -> str:
    payload = {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture(autouse=True)
def _jwt_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)


@pytest.mark.asyncio
async def test_response_always_has_x_request_id_header():
    """Every response must include X-Request-ID regardless of whether one was sent."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert "x-request-id" in resp.headers


@pytest.mark.asyncio
async def test_generated_request_id_is_valid_uuid4():
    """When no X-Request-ID is sent, the generated ID must be a UUID4."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    request_id = resp.headers["x-request-id"]
    assert UUID4_RE.match(request_id), f"Not a UUID4: {request_id!r}"


@pytest.mark.asyncio
async def test_provided_x_request_id_is_echoed_back():
    """When the client provides X-Request-ID, the same value must be returned."""
    custom_id = "my-custom-trace-id-abc123"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.headers["x-request-id"] == custom_id


@pytest.mark.asyncio
async def test_different_requests_get_different_ids():
    """Without client-supplied IDs, each request should get a unique correlation ID."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp1 = await client.get("/health")
        resp2 = await client.get("/health")
    assert resp1.headers["x-request-id"] != resp2.headers["x-request-id"]


@pytest.mark.asyncio
async def test_x_request_id_on_authenticated_route():
    """Correlation IDs must work on protected routes too."""
    token = make_token()
    custom_id = "trace-protected-999"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/protected",
            headers={"Authorization": f"Bearer {token}", "X-Request-ID": custom_id},
        )
    assert resp.status_code == 200
    assert resp.headers["x-request-id"] == custom_id


@pytest.mark.asyncio
async def test_x_request_id_present_on_error_responses():
    """Even 401 responses from auth middleware must carry an X-Request-ID."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/protected")
    assert resp.status_code == 401
    assert "x-request-id" in resp.headers
