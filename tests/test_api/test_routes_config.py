"""Tests for api/routes/config.py — GET /config and PUT /config."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

SECRET = "test-secret-key-32bytes-padded!!"


def make_token(sub: str = "user-1") -> str:
    payload = {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _make_default_config():
    from core.models.config import UserConfig
    return UserConfig()


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    from api.middleware.rate_limit import RateLimitMiddleware
    RateLimitMiddleware.clear_state()
    yield
    RateLimitMiddleware.clear_state()


@pytest.mark.asyncio
async def test_get_config_returns_200(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    app.dependency_overrides[deps.get_config] = _make_default_config

    try:
        token = make_token()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/config",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(deps.get_config, None)


@pytest.mark.asyncio
async def test_get_config_returns_llm_defaults(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    app.dependency_overrides[deps.get_config] = _make_default_config

    try:
        token = make_token()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/config",
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "llm" in data
        assert data["llm"]["provider"] == "claude"
    finally:
        app.dependency_overrides.pop(deps.get_config, None)


@pytest.mark.asyncio
async def test_get_config_requires_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/config")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_put_config_returns_200(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    app.dependency_overrides[deps.get_config] = _make_default_config

    try:
        token = make_token()
        payload = {"llm_provider": "openai", "llm_model": "gpt-4o"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/config",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(deps.get_config, None)


@pytest.mark.asyncio
async def test_put_config_returns_updated_fields(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    app.dependency_overrides[deps.get_config] = _make_default_config

    try:
        token = make_token()
        payload = {"llm_provider": "openai", "llm_model": "gpt-4o"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/config",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "llm_provider" in data["updated_fields"]
        assert "llm_model" in data["updated_fields"]
    finally:
        app.dependency_overrides.pop(deps.get_config, None)


@pytest.mark.asyncio
async def test_put_config_requires_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    payload = {"llm_provider": "openai"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.put("/config", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_put_config_empty_body_returns_200(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    app.dependency_overrides[deps.get_config] = _make_default_config

    try:
        token = make_token()
        payload = {}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/config",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated_fields"] == []
    finally:
        app.dependency_overrides.pop(deps.get_config, None)


@pytest.mark.asyncio
async def test_put_config_all_fields(monkeypatch):
    """Updating all optional fields covers every branch in the PUT handler."""
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    app.dependency_overrides[deps.get_config] = _make_default_config

    try:
        token = make_token()
        payload = {
            "llm_provider": "openai",
            "llm_model": "gpt-4o",
            "llm_endpoint": "http://localhost:1234/v1",
            "patentsview_api_key": "pv-key",
            "serpapi_key": "serp-key",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                "/config",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert resp.status_code == 200
        assert set(data["updated_fields"]) == {
            "llm_provider", "llm_model", "llm_endpoint",
            "patentsview_api_key", "serpapi_key",
        }
    finally:
        app.dependency_overrides.pop(deps.get_config, None)
