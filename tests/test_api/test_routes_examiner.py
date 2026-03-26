"""Tests for api/routes/examiner.py — GET /examiner/ endpoints."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

SECRET = "test-secret-key-32bytes-padded!!"


def make_token(sub: str = "user-1") -> str:
    payload = {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _make_examiner_stats(examiner_id: str = "EX001", art_unit: str = "3621"):
    from core.analysis.examiner_stats import ExaminerStats

    return ExaminerStats(
        examiner_name="John Smith",
        examiner_id=examiner_id,
        art_unit=art_unit,
        allowance_rate=0.65,
        total_applications=200,
        avg_office_actions=1.8,
        specialties=["machine learning"],
    )


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    from api.middleware.rate_limit import RateLimitMiddleware

    RateLimitMiddleware.clear_state()
    yield
    RateLimitMiddleware.clear_state()


# ---------------------------------------------------------------------------
# GET /examiner/art-unit/{art_unit}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_art_unit_returns_200(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    stats_list = [_make_examiner_stats("EX001"), _make_examiner_stats("EX002")]

    with patch(
        "api.routes.examiner.get_examiner_stats",
        new=AsyncMock(return_value=stats_list),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/examiner/art-unit/3621",
                headers={"Authorization": f"Bearer {make_token()}"},
            )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_art_unit_returns_list(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    stats_list = [_make_examiner_stats("EX001"), _make_examiner_stats("EX002")]

    with patch(
        "api.routes.examiner.get_examiner_stats",
        new=AsyncMock(return_value=stats_list),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/examiner/art-unit/3621",
                headers={"Authorization": f"Bearer {make_token()}"},
            )

    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["examiner_id"] == "EX001"


@pytest.mark.asyncio
async def test_get_art_unit_requires_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/examiner/art-unit/3621")

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /examiner/{examiner_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_examiner_returns_200(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    stats = _make_examiner_stats("EX001")

    with patch(
        "api.routes.examiner.lookup_examiner",
        new=AsyncMock(return_value=stats),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/examiner/EX001",
                headers={"Authorization": f"Bearer {make_token()}"},
            )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_examiner_returns_stats(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    stats = _make_examiner_stats("EX001")

    with patch(
        "api.routes.examiner.lookup_examiner",
        new=AsyncMock(return_value=stats),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/examiner/EX001",
                headers={"Authorization": f"Bearer {make_token()}"},
            )

    data = resp.json()
    assert data["examiner_id"] == "EX001"
    assert data["examiner_name"] == "John Smith"
    assert data["allowance_rate"] == 0.65


@pytest.mark.asyncio
async def test_get_examiner_not_found_returns_404(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    with patch(
        "api.routes.examiner.lookup_examiner",
        new=AsyncMock(side_effect=ValueError("Examiner not found")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/examiner/BADID",
                headers={"Authorization": f"Bearer {make_token()}"},
            )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_examiner_requires_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/examiner/EX001")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_art_unit_runtime_error_returns_503(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    with patch(
        "api.routes.examiner.get_examiner_stats",
        new=AsyncMock(side_effect=RuntimeError("PatentsView unavailable")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/examiner/art-unit/3621",
                headers={"Authorization": f"Bearer {make_token()}"},
            )

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_get_examiner_runtime_error_returns_503(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    with patch(
        "api.routes.examiner.lookup_examiner",
        new=AsyncMock(side_effect=RuntimeError("PatentsView timeout")),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/examiner/EX001",
                headers={"Authorization": f"Bearer {make_token()}"},
            )

    assert resp.status_code == 503
