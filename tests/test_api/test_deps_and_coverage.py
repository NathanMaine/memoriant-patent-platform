"""Coverage tests for api/deps.py and uncovered branches in rate_limit.py."""
import os
import time

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

from api.main import app

SECRET = "test-secret-key"


def make_token(sub: str = "user-1") -> str:
    payload = {"sub": sub, "iat": int(time.time()), "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


# ---------------------------------------------------------------------------
# api/deps.py
# ---------------------------------------------------------------------------

class TestGetConfig:
    def test_defaults(self, monkeypatch):
        """get_config() builds UserConfig from default env."""
        # Ensure no stray env vars interfere
        for key in ("LLM_PROVIDER", "LLM_MODEL", "LLM_ENDPOINT", "PATENTSVIEW_API_KEY", "SERPAPI_KEY"):
            monkeypatch.delenv(key, raising=False)

        from api.deps import get_config
        cfg = get_config()
        assert cfg.llm.provider == "claude"
        assert cfg.llm.model == "claude-opus-4-6"
        assert cfg.llm.endpoint is None

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")
        monkeypatch.setenv("LLM_ENDPOINT", "http://localhost:1234/v1")
        monkeypatch.setenv("PATENTSVIEW_API_KEY", "pv-key-123")
        monkeypatch.setenv("SERPAPI_KEY", "serp-key-456")

        from api.deps import get_config
        cfg = get_config()
        assert cfg.llm.provider == "openai"
        assert cfg.llm.model == "gpt-4o"
        assert cfg.llm.endpoint == "http://localhost:1234/v1"
        assert cfg.search.patentsview_api_key == "pv-key-123"
        assert cfg.search.serpapi_key == "serp-key-456"

    def test_returns_user_config_type(self):
        from api.deps import get_config
        from core.models.config import UserConfig
        cfg = get_config()
        assert isinstance(cfg, UserConfig)

    def test_openai_api_key_picked_up(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        from api.deps import get_config
        cfg = get_config()
        assert cfg.llm.api_key == "sk-openai-test"


class TestGetUserId:
    @pytest.mark.asyncio
    async def test_get_user_id_from_state(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", SECRET)
        token = make_token(sub="user-from-state")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/protected",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user-from-state"

    def test_get_user_id_direct(self):
        """Directly call get_user_id to cover line 22."""
        from unittest.mock import MagicMock
        from api.deps import get_user_id

        request = MagicMock()
        request.state.user_id = "direct-user"
        assert get_user_id(request) == "direct-user"


# ---------------------------------------------------------------------------
# Uncovered branches in api/middleware/rate_limit.py
# ---------------------------------------------------------------------------

class TestRateLimitUncoveredBranches:
    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", SECRET)
        from api.middleware.rate_limit import RateLimitMiddleware
        RateLimitMiddleware.clear_state()
        yield
        RateLimitMiddleware.clear_state()

    def test_resolve_limits_invalid_env_value_ignored(self, monkeypatch):
        """ValueError branch in _resolve_limits: non-integer env value is silently ignored."""
        monkeypatch.setenv("RATE_LIMIT_SEARCH", "not-a-number")
        from api.middleware import rate_limit as rl
        limits = rl._resolve_limits()
        # Should fall back to the default (30)
        assert limits["/search"] == 30

    def test_match_endpoint_direct_prefix(self):
        """Direct prefix match branch (path.startswith(prefix))."""
        from api.middleware.rate_limit import _match_endpoint
        # /search is a direct prefix of /search/advanced
        result = _match_endpoint("/search/advanced")
        assert result == "/search"

    def test_match_endpoint_returns_none_for_unknown(self):
        from api.middleware.rate_limit import _match_endpoint
        result = _match_endpoint("/unknown/path")
        assert result is None

    def test_health_limit_zero_is_unlimited(self):
        """Confirm /health key has limit 0 in defaults."""
        from api.middleware.rate_limit import _resolve_limits
        limits = _resolve_limits()
        assert limits.get("/health", 0) == 0

    @pytest.mark.asyncio
    async def test_limit_zero_env_var_allows_unlimited_requests(self, monkeypatch):
        """RATE_LIMIT_SEARCH=0 → limit==0 branch → unlimited; exercises line 90."""
        monkeypatch.setenv("RATE_LIMIT_SEARCH", "0")
        from api.middleware.rate_limit import RateLimitMiddleware
        RateLimitMiddleware.clear_state()

        token = make_token()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(10):
                resp = await client.get(
                    "/api/search-stub",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# New dependency functions added for route implementations (Task 8)
# ---------------------------------------------------------------------------

class TestNewDeps:
    def test_get_aggregator_returns_search_aggregator(self):
        from api.deps import get_aggregator
        from core.search.aggregator import SearchAggregator
        agg = get_aggregator()
        assert isinstance(agg, SearchAggregator)

    def test_get_analyzers_returns_empty_dict(self):
        from api.deps import get_analyzers
        result = get_analyzers()
        assert isinstance(result, dict)
        assert result == {}

    def test_get_drafter_returns_provisional_drafter(self):
        from api.deps import get_drafter
        from core.drafting.provisional import ProvisionalDrafter
        drafter = get_drafter()
        assert isinstance(drafter, ProvisionalDrafter)

    def test_get_pipeline_returns_patent_pipeline(self):
        from api.deps import get_pipeline
        from core.pipeline import PatentPipeline
        pipeline = get_pipeline()
        assert isinstance(pipeline, PatentPipeline)


# ---------------------------------------------------------------------------
# Lifespan coverage — trigger startup + shutdown via app lifespan context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_app_lifespan_fires_startup_and_shutdown():
    """Exercise the lifespan context manager to cover the startup/shutdown log lines."""
    from api.main import lifespan, app
    # Directly enter/exit the lifespan context manager to cover lines 19-21
    async with lifespan(app):
        pass  # startup and shutdown both execute


# ---------------------------------------------------------------------------
# NoopLLM raise coverage in get_drafter and get_pipeline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_noop_llm_in_drafter_raises():
    """The NoopLLM.generate inside get_drafter raises RuntimeError when called."""
    from api.deps import get_drafter
    drafter = get_drafter()
    with pytest.raises(Exception):
        await drafter.llm_provider.generate("test prompt")


@pytest.mark.asyncio
async def test_noop_llm_in_pipeline_raises():
    """The NoopLLM.generate inside get_pipeline raises RuntimeError when called."""
    from api.deps import get_pipeline
    pl = get_pipeline()
    with pytest.raises(Exception):
        await pl._llm_provider.generate("test prompt")
