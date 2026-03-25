"""Tests for search provider base interface and registry.

Tests follow TDD: written before implementation.
"""
from __future__ import annotations

import pytest

from core.search.base import SearchProvider, SearchQuery, SearchResponse
from core.search.registry import SearchRegistry, _PROVIDERS, register_provider


# ---------------------------------------------------------------------------
# Dummy concrete provider for registry tests
# ---------------------------------------------------------------------------


class _DummyProvider(SearchProvider):
    """Minimal concrete SearchProvider used only in tests."""

    provider_name: str = "dummy"

    def search(self, query: SearchQuery) -> SearchResponse:
        return SearchResponse(results=[], provider=self.provider_name, duration_ms=0)

    def health_check(self) -> bool:
        return True


class _DummyProviderB(SearchProvider):
    """Second dummy provider to test multi-provider scenarios."""

    provider_name: str = "dummy_b"

    def search(self, query: SearchQuery) -> SearchResponse:
        return SearchResponse(results=[], provider=self.provider_name, duration_ms=0)

    def health_check(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# SearchQuery tests
# ---------------------------------------------------------------------------


class TestSearchQuery:
    def test_default_values(self):
        q = SearchQuery(query="neural network")
        assert q.query == "neural network"
        assert q.strategies == ["keyword"]
        assert q.date_range is None
        assert q.cpc_codes == []
        assert q.inventors == []
        assert q.assignees == []
        assert q.max_results == 50

    def test_custom_values(self):
        q = SearchQuery(
            query="battery",
            strategies=["keyword", "classification"],
            date_range={"start": "2020-01-01", "end": "2024-12-31"},
            cpc_codes=["H01M", "H02J"],
            inventors=["Tesla, Nikola"],
            assignees=["Acme Corp"],
            max_results=100,
        )
        assert q.strategies == ["keyword", "classification"]
        assert q.date_range == {"start": "2020-01-01", "end": "2024-12-31"}
        assert q.cpc_codes == ["H01M", "H02J"]
        assert q.inventors == ["Tesla, Nikola"]
        assert q.assignees == ["Acme Corp"]
        assert q.max_results == 100

    def test_empty_query_string_allowed(self):
        # Pydantic does not restrict empty strings unless we add a validator
        q = SearchQuery(query="")
        assert q.query == ""

    def test_strategies_default_is_new_list_per_instance(self):
        q1 = SearchQuery(query="a")
        q2 = SearchQuery(query="b")
        q1.strategies.append("classification")
        assert q2.strategies == ["keyword"], "default lists must not be shared"


# ---------------------------------------------------------------------------
# SearchResponse tests
# ---------------------------------------------------------------------------


class TestSearchResponse:
    def test_default_values(self):
        resp = SearchResponse(results=[], provider="patentsview", duration_ms=42)
        assert resp.results == []
        assert resp.provider == "patentsview"
        assert resp.duration_ms == 42
        assert resp.total_hits == 0
        assert resp.error is None

    def test_with_error(self):
        resp = SearchResponse(
            results=[], provider="patentsview", duration_ms=0, error="timeout"
        )
        assert resp.error == "timeout"

    def test_total_hits(self):
        resp = SearchResponse(results=[], provider="patentsview", duration_ms=10, total_hits=999)
        assert resp.total_hits == 999


# ---------------------------------------------------------------------------
# SearchProvider abstract class tests
# ---------------------------------------------------------------------------


class TestSearchProviderABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            SearchProvider()  # type: ignore[abstract]

    def test_concrete_subclass_requires_search(self):
        """A class missing search() cannot be instantiated."""

        class _Incomplete(SearchProvider):
            provider_name: str = "incomplete"

            def health_check(self) -> bool:
                return True

        with pytest.raises(TypeError):
            _Incomplete()  # type: ignore[abstract]

    def test_concrete_subclass_requires_health_check(self):
        """A class missing health_check() cannot be instantiated."""

        class _Incomplete(SearchProvider):
            provider_name: str = "incomplete2"

            def search(self, query: SearchQuery) -> SearchResponse:
                return SearchResponse(results=[], provider="x", duration_ms=0)

        with pytest.raises(TypeError):
            _Incomplete()  # type: ignore[abstract]

    def test_dummy_provider_instantiates(self):
        p = _DummyProvider()
        assert p.provider_name == "dummy"

    def test_dummy_provider_search_returns_response(self):
        p = _DummyProvider()
        q = SearchQuery(query="test")
        resp = p.search(q)
        assert isinstance(resp, SearchResponse)
        assert resp.provider == "dummy"

    def test_dummy_provider_health_check(self):
        p = _DummyProvider()
        assert p.health_check() is True


# ---------------------------------------------------------------------------
# SearchRegistry tests
# ---------------------------------------------------------------------------


class TestSearchRegistry:
    """Tests for SearchRegistry and register_provider."""

    def setup_method(self):
        """Capture state of _PROVIDERS before each test so we can restore it."""
        self._original_providers = dict(_PROVIDERS)

    def teardown_method(self):
        """Restore _PROVIDERS to pre-test state to avoid test pollution."""
        _PROVIDERS.clear()
        _PROVIDERS.update(self._original_providers)

    # --- list_providers ---

    def test_list_providers_returns_list(self):
        result = SearchRegistry.list_providers()
        assert isinstance(result, list)

    def test_list_providers_includes_registered(self):
        register_provider("dummy", _DummyProvider)
        assert "dummy" in SearchRegistry.list_providers()

    def test_list_providers_after_multiple_registrations(self):
        register_provider("dummy", _DummyProvider)
        register_provider("dummy_b", _DummyProviderB)
        providers = SearchRegistry.list_providers()
        assert "dummy" in providers
        assert "dummy_b" in providers

    # --- create ---

    def test_create_known_provider(self):
        register_provider("dummy", _DummyProvider)
        p = SearchRegistry.create("dummy")
        assert isinstance(p, _DummyProvider)
        assert p.provider_name == "dummy"

    def test_create_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="unknown"):
            SearchRegistry.create("nonexistent_provider_xyz")

    def test_create_passes_kwargs_to_provider(self):
        """Kwargs are forwarded; _DummyProvider ignores extras via model_config."""

        class _KwargProvider(SearchProvider):
            provider_name: str = "kwarg"
            api_key: str = ""

            def search(self, query: SearchQuery) -> SearchResponse:
                return SearchResponse(results=[], provider=self.provider_name, duration_ms=0)

            def health_check(self) -> bool:
                return True

        register_provider("kwarg", _KwargProvider)
        p = SearchRegistry.create("kwarg", api_key="secret")
        assert isinstance(p, _KwargProvider)
        assert p.api_key == "secret"

    # --- get_enabled ---

    def test_get_enabled_default_flags(self):
        """With default flags, patentsview and uspto_odp should be returned."""
        # Register stub providers for the built-in names
        register_provider("patentsview", _DummyProvider)
        register_provider("uspto_odp", _DummyProviderB)
        register_provider("serpapi", _DummyProvider)

        enabled = SearchRegistry.get_enabled(
            patentsview_enabled=True,
            uspto_odp_enabled=True,
            serpapi_enabled=False,
        )
        names = [p.provider_name for p in enabled]
        # Both enabled providers should appear
        assert "dummy" in names or any(isinstance(p, (_DummyProvider, _DummyProviderB)) for p in enabled)
        assert len(enabled) == 2

    def test_get_enabled_all_disabled(self):
        register_provider("patentsview", _DummyProvider)
        register_provider("uspto_odp", _DummyProviderB)
        register_provider("serpapi", _DummyProvider)

        enabled = SearchRegistry.get_enabled(
            patentsview_enabled=False,
            uspto_odp_enabled=False,
            serpapi_enabled=False,
        )
        assert enabled == []

    def test_get_enabled_serpapi_only(self):
        register_provider("patentsview", _DummyProvider)
        register_provider("uspto_odp", _DummyProviderB)
        register_provider("serpapi", _DummyProvider)

        enabled = SearchRegistry.get_enabled(
            patentsview_enabled=False,
            uspto_odp_enabled=False,
            serpapi_enabled=True,
        )
        assert len(enabled) == 1

    def test_get_enabled_returns_provider_instances(self):
        register_provider("patentsview", _DummyProvider)
        register_provider("uspto_odp", _DummyProviderB)
        register_provider("serpapi", _DummyProvider)

        enabled = SearchRegistry.get_enabled(
            patentsview_enabled=True,
            uspto_odp_enabled=False,
            serpapi_enabled=False,
        )
        assert len(enabled) == 1
        assert isinstance(enabled[0], SearchProvider)

    def test_get_enabled_skips_unregistered_providers(self):
        """If a named provider is not registered, it is silently skipped."""
        # Do NOT register anything — start from empty _PROVIDERS
        _PROVIDERS.clear()
        enabled = SearchRegistry.get_enabled(
            patentsview_enabled=True,
            uspto_odp_enabled=True,
            serpapi_enabled=True,
        )
        assert enabled == []

    # --- register_provider module-level function ---

    def test_register_provider_adds_to_registry(self):
        register_provider("dummy", _DummyProvider)
        assert "dummy" in _PROVIDERS
        assert _PROVIDERS["dummy"] is _DummyProvider

    def test_register_provider_overwrites_existing(self):
        register_provider("dummy", _DummyProvider)
        register_provider("dummy", _DummyProviderB)
        assert _PROVIDERS["dummy"] is _DummyProviderB
