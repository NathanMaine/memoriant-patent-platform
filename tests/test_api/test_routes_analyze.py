"""Tests for api/routes/analyze.py — POST /analyze."""
from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

SECRET = "test-secret-key-32bytes-padded!!"


def make_token(sub: str = "user-1") -> str:
    payload = {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _make_analysis_result(module: str = "novelty", status: str = "clear"):
    from core.analysis.base import AnalysisResult, AnalysisStatus
    return AnalysisResult(
        module=module,
        status=AnalysisStatus(status),
        findings=[],
        recommendation=f"{module} looks good.",
    )


def _make_mock_analyzer(module_name: str = "novelty", status: str = "clear"):
    mock = MagicMock()
    mock.module_name = module_name
    mock.analyze = AsyncMock(return_value=_make_analysis_result(module_name, status))
    return mock


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    from api.middleware.rate_limit import RateLimitMiddleware
    RateLimitMiddleware.clear_state()
    yield
    RateLimitMiddleware.clear_state()


@pytest.mark.asyncio
async def test_analyze_returns_200(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_analyzers = {"novelty": _make_mock_analyzer("novelty")}
    app.dependency_overrides[deps.get_analyzers] = lambda: mock_analyzers

    try:
        token = make_token()
        payload = {
            "project_id": "proj-123",
            "invention_description": "A novel battery electrode.",
            "checks": ["novelty"],
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/analyze",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(deps.get_analyzers, None)


@pytest.mark.asyncio
async def test_analyze_returns_project_id(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_analyzers = {"novelty": _make_mock_analyzer("novelty")}
    app.dependency_overrides[deps.get_analyzers] = lambda: mock_analyzers

    try:
        token = make_token()
        payload = {
            "project_id": "proj-xyz",
            "invention_description": "Battery.",
            "checks": ["novelty"],
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/analyze",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert data["project_id"] == "proj-xyz"
    finally:
        app.dependency_overrides.pop(deps.get_analyzers, None)


@pytest.mark.asyncio
async def test_analyze_returns_checks_completed(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_analyzers = {
        "novelty": _make_mock_analyzer("novelty"),
        "obviousness": _make_mock_analyzer("obviousness"),
    }
    app.dependency_overrides[deps.get_analyzers] = lambda: mock_analyzers

    try:
        token = make_token()
        payload = {
            "project_id": "proj-checks",
            "invention_description": "A thing.",
            "checks": ["novelty", "obviousness"],
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/analyze",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "novelty" in data["checks_completed"]
        assert "obviousness" in data["checks_completed"]
    finally:
        app.dependency_overrides.pop(deps.get_analyzers, None)


@pytest.mark.asyncio
async def test_analyze_skips_unrequested_checks(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    novelty_mock = _make_mock_analyzer("novelty")
    obviousness_mock = _make_mock_analyzer("obviousness")
    mock_analyzers = {"novelty": novelty_mock, "obviousness": obviousness_mock}
    app.dependency_overrides[deps.get_analyzers] = lambda: mock_analyzers

    try:
        token = make_token()
        payload = {
            "project_id": "proj-skip",
            "invention_description": "Skip test.",
            "checks": ["novelty"],  # only novelty requested
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/analyze",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "novelty" in data["checks_completed"]
        assert "obviousness" not in data["checks_completed"]
        obviousness_mock.analyze.assert_not_called()
    finally:
        app.dependency_overrides.pop(deps.get_analyzers, None)


@pytest.mark.asyncio
async def test_analyze_requires_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    payload = {
        "project_id": "proj-1",
        "invention_description": "test",
        "checks": ["novelty"],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/analyze", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_analyze_returns_analysis_id(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_analyzers = {"novelty": _make_mock_analyzer("novelty")}
    app.dependency_overrides[deps.get_analyzers] = lambda: mock_analyzers

    try:
        token = make_token()
        payload = {
            "project_id": "proj-id-check",
            "invention_description": "test.",
            "checks": ["novelty"],
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/analyze",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "analysis_id" in data
        assert len(data["analysis_id"]) > 0
    finally:
        app.dependency_overrides.pop(deps.get_analyzers, None)


@pytest.mark.asyncio
async def test_analyze_returns_summary(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_analyzers = {"novelty": _make_mock_analyzer("novelty")}
    app.dependency_overrides[deps.get_analyzers] = lambda: mock_analyzers

    try:
        token = make_token()
        payload = {
            "project_id": "proj-summary",
            "invention_description": "test.",
            "checks": ["novelty"],
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/analyze",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "summary" in data
        assert isinstance(data["summary"], str)
    finally:
        app.dependency_overrides.pop(deps.get_analyzers, None)


@pytest.mark.asyncio
async def test_analyze_module_not_found_skipped(monkeypatch):
    """Requesting a check for which no module is registered is silently skipped."""
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    # No modules registered at all
    app.dependency_overrides[deps.get_analyzers] = lambda: {}

    try:
        token = make_token()
        payload = {
            "project_id": "proj-missing",
            "invention_description": "test.",
            "checks": ["nonexistent_check"],
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/analyze",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert resp.status_code == 200
        assert data["checks_completed"] == []
        assert "No checks completed" in data["summary"]
    finally:
        app.dependency_overrides.pop(deps.get_analyzers, None)
