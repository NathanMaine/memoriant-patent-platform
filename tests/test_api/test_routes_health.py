"""Tests for api/routes/health.py — GET /health."""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport


def _make_app():
    from api.main import app
    return app


@pytest.mark.asyncio
async def test_health_returns_200():
    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_returns_status_healthy():
    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_returns_version():
    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    data = resp.json()
    assert "version" in data
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_health_returns_services():
    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    data = resp.json()
    assert "services" in data
    assert isinstance(data["services"], dict)
