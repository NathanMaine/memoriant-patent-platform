"""Tests for api/routes/draft.py — POST /draft."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

SECRET = "test-secret-key-32bytes-padded!!"


def make_token(sub: str = "user-1") -> str:
    payload = {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _make_draft_application(filing_format: str = "provisional"):
    from core.models.application import DraftApplication, FilingFormat, Specification
    spec = Specification(
        background="Background text.",
        summary="Summary text.",
        detailed_description="Detailed description.",
        embodiments=[],
    )
    return DraftApplication(
        filing_format=FilingFormat(filing_format),
        title="Test Patent Application",
        abstract="A brief abstract under 150 words.",
        specification=spec,
        claims=[],
    )


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    from api.middleware.rate_limit import RateLimitMiddleware
    RateLimitMiddleware.clear_state()
    yield
    RateLimitMiddleware.clear_state()


@pytest.mark.asyncio
async def test_draft_returns_200(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_drafter = MagicMock()
    mock_drafter.draft = AsyncMock(return_value=_make_draft_application("provisional"))
    app.dependency_overrides[deps.get_drafter] = lambda: mock_drafter

    try:
        token = make_token()
        payload = {
            "project_id": "proj-123",
            "filing_format": "provisional",
            "invention_description": "A novel battery electrode system.",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/draft",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(deps.get_drafter, None)


@pytest.mark.asyncio
async def test_draft_returns_project_id(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_drafter = MagicMock()
    mock_drafter.draft = AsyncMock(return_value=_make_draft_application("provisional"))
    app.dependency_overrides[deps.get_drafter] = lambda: mock_drafter

    try:
        token = make_token()
        payload = {
            "project_id": "proj-draft-test",
            "filing_format": "provisional",
            "invention_description": "An invention.",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/draft",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert data["project_id"] == "proj-draft-test"
    finally:
        app.dependency_overrides.pop(deps.get_drafter, None)


@pytest.mark.asyncio
async def test_draft_returns_filing_format(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_drafter = MagicMock()
    mock_drafter.draft = AsyncMock(return_value=_make_draft_application("nonprovisional"))
    app.dependency_overrides[deps.get_drafter] = lambda: mock_drafter

    try:
        token = make_token()
        payload = {
            "project_id": "proj-np",
            "filing_format": "nonprovisional",
            "invention_description": "An invention.",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/draft",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert data["filing_format"] == "nonprovisional"
    finally:
        app.dependency_overrides.pop(deps.get_drafter, None)


@pytest.mark.asyncio
async def test_draft_returns_draft_id(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_drafter = MagicMock()
    mock_drafter.draft = AsyncMock(return_value=_make_draft_application("provisional"))
    app.dependency_overrides[deps.get_drafter] = lambda: mock_drafter

    try:
        token = make_token()
        payload = {
            "project_id": "proj-id",
            "filing_format": "provisional",
            "invention_description": "An invention.",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/draft",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "draft_id" in data
        assert len(data["draft_id"]) > 0
    finally:
        app.dependency_overrides.pop(deps.get_drafter, None)


@pytest.mark.asyncio
async def test_draft_requires_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    payload = {
        "project_id": "proj-1",
        "filing_format": "provisional",
        "invention_description": "test",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/draft", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_draft_pct_format(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_drafter = MagicMock()
    mock_drafter.draft = AsyncMock(return_value=_make_draft_application("pct"))
    app.dependency_overrides[deps.get_drafter] = lambda: mock_drafter

    try:
        token = make_token()
        payload = {
            "project_id": "proj-pct",
            "filing_format": "pct",
            "invention_description": "An international invention.",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/draft",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert resp.status_code == 200
        assert data["filing_format"] == "pct"
    finally:
        app.dependency_overrides.pop(deps.get_drafter, None)


@pytest.mark.asyncio
async def test_draft_returns_sections_list(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_drafter = MagicMock()
    mock_drafter.draft = AsyncMock(return_value=_make_draft_application("provisional"))
    app.dependency_overrides[deps.get_drafter] = lambda: mock_drafter

    try:
        token = make_token()
        payload = {
            "project_id": "proj-sections",
            "filing_format": "provisional",
            "invention_description": "An invention.",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/draft",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "sections" in data
        assert isinstance(data["sections"], list)
    finally:
        app.dependency_overrides.pop(deps.get_drafter, None)
