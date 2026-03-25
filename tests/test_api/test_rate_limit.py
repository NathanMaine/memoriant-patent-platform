"""Tests for per-user per-endpoint rate limiting middleware (Task 7)."""
import time

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

from api.main import app

SECRET = "test-secret-key"


def make_token(sub: str = "user-1") -> str:
    payload = {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    # Set very low limits so we can hit them quickly in tests
    monkeypatch.setenv("RATE_LIMIT_SEARCH", "3")
    monkeypatch.setenv("RATE_LIMIT_ANALYZE", "2")
    monkeypatch.setenv("RATE_LIMIT_DRAFT", "1")
    monkeypatch.setenv("RATE_LIMIT_PIPELINE", "1")
    monkeypatch.setenv("RATE_LIMIT_CONFIG", "2")


@pytest.fixture(autouse=True)
def _clear_rate_state():
    """Reset rate limit state between tests."""
    from api.middleware.rate_limit import RateLimitMiddleware
    RateLimitMiddleware.clear_state()
    yield
    RateLimitMiddleware.clear_state()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_under_limit_passes():
    token = make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 3 requests under a limit of 3 should all pass
        for _ in range(3):
            resp = await client.get(
                "/api/search-stub",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_at_limit_returns_429():
    token = make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(3):
            await client.get(
                "/api/search-stub",
                headers={"Authorization": f"Bearer {token}"},
            )
        resp = await client.get(
            "/api/search-stub",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


@pytest.mark.asyncio
async def test_retry_after_header_present_on_429():
    token = make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(4):
            resp = await client.get(
                "/api/search-stub",
                headers={"Authorization": f"Bearer {token}"},
            )
    assert resp.status_code == 429
    retry_after = int(resp.headers["Retry-After"])
    assert 0 <= retry_after <= 60


@pytest.mark.asyncio
async def test_different_users_have_separate_limits():
    token_a = make_token(sub="user-a")
    token_b = make_token(sub="user-b")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Exhaust user-a's limit
        for _ in range(4):
            resp_a = await client.get(
                "/api/search-stub",
                headers={"Authorization": f"Bearer {token_a}"},
            )
        # user-b should still pass
        resp_b = await client.get(
            "/api/search-stub",
            headers={"Authorization": f"Bearer {token_b}"},
        )
    assert resp_a.status_code == 429
    assert resp_b.status_code == 200


@pytest.mark.asyncio
async def test_different_endpoints_have_different_limits():
    """Analyze limit (2) is lower than search limit (3) in test env."""
    token = make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Use analyze-stub (limit=2): 3rd should fail
        for _ in range(2):
            await client.get(
                "/api/analyze-stub",
                headers={"Authorization": f"Bearer {token}"},
            )
        resp = await client.get(
            "/api/analyze-stub",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_health_endpoint_is_exempt():
    """Health endpoint has unlimited rate."""
    token = make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(50):
            resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_expired_timestamps_do_not_count():
    """After the 60-second window, old requests should not count."""
    from api.middleware.rate_limit import RateLimitMiddleware

    token = make_token()
    user_id = "user-1"
    endpoint = "/api/search-stub"

    # Manually inject 3 very old timestamps (61 seconds ago)
    key = f"{user_id}:{endpoint}"
    old_ts = time.time() - 61
    RateLimitMiddleware._state[key] = [old_ts, old_ts, old_ts]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/search-stub",
            headers={"Authorization": f"Bearer {token}"},
        )
    # Old timestamps should be cleaned up; request should pass
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_draft_stub_limit():
    token = make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/api/draft-stub", headers={"Authorization": f"Bearer {token}"})
        resp = await client.get(
            "/api/draft-stub", headers={"Authorization": f"Bearer {token}"}
        )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_config_stub_limit():
    token = make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(2):
            await client.get("/api/config-stub", headers={"Authorization": f"Bearer {token}"})
        resp = await client.get(
            "/api/config-stub", headers={"Authorization": f"Bearer {token}"}
        )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_pipeline_stub_limit():
    token = make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get(
            "/api/pipeline-stub", headers={"Authorization": f"Bearer {token}"}
        )
        resp = await client.get(
            "/api/pipeline-stub", headers={"Authorization": f"Bearer {token}"}
        )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_429_response_body_contains_message():
    token = make_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(4):
            resp = await client.get(
                "/api/search-stub",
                headers={"Authorization": f"Bearer {token}"},
            )
    assert resp.status_code == 429
    body = resp.json()
    assert "detail" in body
