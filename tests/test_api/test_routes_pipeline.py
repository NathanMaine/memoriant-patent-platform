"""Tests for api/routes/pipeline.py — POST /pipeline."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

SECRET = "test-secret-key-32bytes-padded!!"


def make_token(sub: str = "user-1") -> str:
    payload = {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _make_pipeline_result(project_id: str = "proj-pipe"):
    from core.pipeline import PipelineResult, PipelineStage
    return PipelineResult(
        project_id=project_id,
        stages_completed=[
            PipelineStage.DESCRIBE,
            PipelineStage.SEARCH,
            PipelineStage.ANALYZE,
            PipelineStage.DRAFT,
            PipelineStage.COMPLETE,
        ],
        current_stage=PipelineStage.COMPLETE,
        gate_blocked=False,
        error=None,
    )


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    from api.middleware.rate_limit import RateLimitMiddleware
    RateLimitMiddleware.clear_state()
    yield
    RateLimitMiddleware.clear_state()


@pytest.mark.asyncio
async def test_pipeline_returns_200(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_pipeline = MagicMock()
    mock_pipeline.run = AsyncMock(return_value=_make_pipeline_result("proj-1"))
    app.dependency_overrides[deps.get_pipeline] = lambda: mock_pipeline

    try:
        token = make_token()
        payload = {
            "project_id": "proj-1",
            "invention_description": "An innovative battery.",
            "filing_format": "provisional",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/pipeline",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(deps.get_pipeline, None)


@pytest.mark.asyncio
async def test_pipeline_returns_project_id(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_pipeline = MagicMock()
    mock_pipeline.run = AsyncMock(return_value=_make_pipeline_result("proj-id-check"))
    app.dependency_overrides[deps.get_pipeline] = lambda: mock_pipeline

    try:
        token = make_token()
        payload = {
            "project_id": "proj-id-check",
            "invention_description": "A test invention.",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/pipeline",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert data["project_id"] == "proj-id-check"
    finally:
        app.dependency_overrides.pop(deps.get_pipeline, None)


@pytest.mark.asyncio
async def test_pipeline_returns_stages_completed(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_pipeline = MagicMock()
    mock_pipeline.run = AsyncMock(return_value=_make_pipeline_result("proj-stages"))
    app.dependency_overrides[deps.get_pipeline] = lambda: mock_pipeline

    try:
        token = make_token()
        payload = {
            "project_id": "proj-stages",
            "invention_description": "An invention.",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/pipeline",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "stages_completed" in data
        assert isinstance(data["stages_completed"], list)
        assert len(data["stages_completed"]) > 0
    finally:
        app.dependency_overrides.pop(deps.get_pipeline, None)


@pytest.mark.asyncio
async def test_pipeline_returns_status(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_pipeline = MagicMock()
    mock_pipeline.run = AsyncMock(return_value=_make_pipeline_result("proj-status"))
    app.dependency_overrides[deps.get_pipeline] = lambda: mock_pipeline

    try:
        token = make_token()
        payload = {
            "project_id": "proj-status",
            "invention_description": "An invention.",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/pipeline",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "status" in data
    finally:
        app.dependency_overrides.pop(deps.get_pipeline, None)


@pytest.mark.asyncio
async def test_pipeline_requires_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    payload = {
        "project_id": "proj-1",
        "invention_description": "test",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/pipeline", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_pipeline_returns_pipeline_id(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_pipeline = MagicMock()
    mock_pipeline.run = AsyncMock(return_value=_make_pipeline_result("proj-pipeid"))
    app.dependency_overrides[deps.get_pipeline] = lambda: mock_pipeline

    try:
        token = make_token()
        payload = {
            "project_id": "proj-pipeid",
            "invention_description": "An invention.",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/pipeline",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "pipeline_id" in data
        assert len(data["pipeline_id"]) > 0
    finally:
        app.dependency_overrides.pop(deps.get_pipeline, None)


@pytest.mark.asyncio
async def test_pipeline_no_project_id_auto_generates(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_pipeline = MagicMock()

    async def _run_with_auto_id(**kwargs):
        project_id = kwargs.get("project_id") or "auto-generated-id"
        return _make_pipeline_result(project_id)

    mock_pipeline.run = AsyncMock(side_effect=_run_with_auto_id)
    app.dependency_overrides[deps.get_pipeline] = lambda: mock_pipeline

    try:
        token = make_token()
        payload = {"invention_description": "No project id here."}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/pipeline",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "project_id" in data
    finally:
        app.dependency_overrides.pop(deps.get_pipeline, None)
