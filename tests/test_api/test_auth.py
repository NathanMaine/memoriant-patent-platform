"""Tests for JWT auth middleware (Task 6)."""
import time

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

from api.main import app

SECRET = "test-secret-key"


def make_token(
    *,
    secret: str = SECRET,
    sub: str = "user-42",
    exp_offset: int = 3600,
    algorithm: str = "HS256",
    payload_extra: dict | None = None,
) -> str:
    """Create a JWT for testing."""
    payload = {"sub": sub, "iat": int(time.time())}
    if exp_offset is not None:
        payload["exp"] = int(time.time()) + exp_offset
    if payload_extra:
        payload.update(payload_extra)
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)


# ---------------------------------------------------------------------------
# Helper: make a protected route available on the test app
# ---------------------------------------------------------------------------

async def _get_app_client():
    """Return an AsyncClient wired to the test app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_jwt_sets_user_id(auth_env):
    token = make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health", headers={"Authorization": f"Bearer {token}"})
    # Health is public but we verify no crash with a valid token present
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_missing_auth_header_returns_401(auth_env):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/protected")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authorization header missing"


@pytest.mark.asyncio
async def test_invalid_signature_returns_401(auth_env):
    token = make_token(secret="wrong-secret")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_expired_token_returns_401(auth_env):
    token = make_token(exp_offset=-10)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token expired"


@pytest.mark.asyncio
async def test_malformed_bearer_prefix_returns_401(auth_env):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/protected", headers={"Authorization": "Token abc123"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authorization header must use Bearer scheme"


@pytest.mark.asyncio
async def test_bearer_with_empty_token_returns_401(auth_env):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/protected", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_endpoint_skips_auth(auth_env):
    """Health endpoint must NOT require a token."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_docs_endpoint_skips_auth(auth_env):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/docs")
    # FastAPI returns 200 for docs
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_openapi_json_skips_auth(auth_env):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_valid_token_user_id_propagated(auth_env):
    """Valid token → user_id echoed back from protected route."""
    token = make_token(sub="user-99")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "user-99"


@pytest.mark.asyncio
async def test_garbage_token_returns_401(auth_env):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/protected", headers={"Authorization": "Bearer not.a.jwt"}
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token"
