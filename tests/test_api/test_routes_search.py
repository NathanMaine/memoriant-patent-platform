"""Tests for api/routes/search.py — POST /search."""
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


def _make_search_result(patent_id: str = "US1234567") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "patent_id": patent_id,
        "title": "Test Patent",
        "abstract": "A test abstract.",
        "patent_date": None,
        "patent_type": None,
        "inventors": [],
        "assignees": [],
        "cpc_codes": [],
        "citations": [],
        "relevance_score": 0.95,
        "relevance_notes": None,
        "provider": "test",
        "strategy": "keyword",
    }


def _make_aggregated_response(results=None):
    from core.search.aggregator import AggregatedSearchResponse
    from core.models.patent import SearchResult, SearchStrategy

    sr_list = []
    for r in (results or []):
        sr_list.append(SearchResult(**r))

    return AggregatedSearchResponse(
        results=sr_list,
        total_hits=len(sr_list),
        provider_responses=[],
        duration_ms=10,
        errors=[],
    )


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    from api.middleware.rate_limit import RateLimitMiddleware
    RateLimitMiddleware.clear_state()
    yield
    RateLimitMiddleware.clear_state()


@pytest.mark.asyncio
async def test_search_returns_200(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_agg = MagicMock()
    mock_agg.search = AsyncMock(
        return_value=_make_aggregated_response([_make_search_result()])
    )

    app.dependency_overrides[deps.get_aggregator] = lambda: mock_agg
    try:
        token = make_token()
        payload = {"query": "battery electrode", "max_results": 5}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/search",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(deps.get_aggregator, None)


@pytest.mark.asyncio
async def test_search_returns_results(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_agg = MagicMock()
    mock_agg.search = AsyncMock(
        return_value=_make_aggregated_response([_make_search_result("US9999999")])
    )

    app.dependency_overrides[deps.get_aggregator] = lambda: mock_agg
    try:
        token = make_token()
        payload = {"query": "fuel cell innovation"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/search",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert data["total"] == 1
        assert len(data["results"]) == 1
        assert data["query"] == "fuel cell innovation"
    finally:
        app.dependency_overrides.pop(deps.get_aggregator, None)


@pytest.mark.asyncio
async def test_search_empty_results(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_agg = MagicMock()
    mock_agg.search = AsyncMock(return_value=_make_aggregated_response([]))

    app.dependency_overrides[deps.get_aggregator] = lambda: mock_agg
    try:
        token = make_token()
        payload = {"query": "completely novel invention xyz"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/search",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert resp.status_code == 200
        assert data["results"] == []
        assert data["total"] == 0
    finally:
        app.dependency_overrides.pop(deps.get_aggregator, None)


@pytest.mark.asyncio
async def test_search_requires_auth(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app

    payload = {"query": "test"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/search", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_includes_project_id(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_agg = MagicMock()
    mock_agg.search = AsyncMock(return_value=_make_aggregated_response([]))

    app.dependency_overrides[deps.get_aggregator] = lambda: mock_agg
    try:
        token = make_token()
        payload = {"query": "test query", "project_id": "proj-abc"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/search",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert data["project_id"] == "proj-abc"
    finally:
        app.dependency_overrides.pop(deps.get_aggregator, None)


@pytest.mark.asyncio
async def test_search_uses_strategies_from_request(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_agg = MagicMock()
    mock_agg.search = AsyncMock(return_value=_make_aggregated_response([]))

    app.dependency_overrides[deps.get_aggregator] = lambda: mock_agg
    try:
        token = make_token()
        payload = {"query": "test", "strategies": ["keyword", "classification"]}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/search",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "keyword" in data["strategies_used"]
        assert "classification" in data["strategies_used"]
    finally:
        app.dependency_overrides.pop(deps.get_aggregator, None)


@pytest.mark.asyncio
async def test_search_no_project_id_generates_one(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    from api.main import app
    from api import deps

    mock_agg = MagicMock()
    mock_agg.search = AsyncMock(return_value=_make_aggregated_response([]))

    app.dependency_overrides[deps.get_aggregator] = lambda: mock_agg
    try:
        token = make_token()
        payload = {"query": "no project id test"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/search",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        data = resp.json()
        assert "project_id" in data
        assert data["project_id"] is not None
        assert len(data["project_id"]) > 0
    finally:
        app.dependency_overrides.pop(deps.get_aggregator, None)
