"""Tests for the Semantic Scholar NPL search provider.

Written before implementation (TDD). All tests mock httpx.Client
to avoid real network calls.

API: GET https://api.semanticscholar.org/graph/v1/paper/search?query=...
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from core.search.base import SearchQuery, SearchResponse
from core.search.registry import SearchRegistry, _PROVIDERS


# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

SAMPLE_PAPER = {
    "paperId": "abc123def456",
    "title": "Deep Learning for Patent Classification",
    "abstract": "We propose a deep learning approach for classifying patents.",
    "tldr": {"text": "A deep learning method for patent classification."},
}

SAMPLE_RESPONSE = {
    "data": [SAMPLE_PAPER],
    "total": 1,
    "offset": 0,
    "next": None,
}

EMPTY_RESPONSE: dict = {
    "data": [],
    "total": 0,
    "offset": 0,
}


def _make_mock_response(status_code: int, body: dict) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    return resp


def _make_sync_client(mock_response: MagicMock) -> MagicMock:
    """Return a mock httpx.Client whose get() returns mock_response."""
    client = MagicMock()
    client.get = MagicMock(return_value=mock_response)
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------


def test_semantic_scholar_module_importable():
    """The module must import without errors."""
    import core.search.semantic_scholar  # noqa: F401


# ---------------------------------------------------------------------------
# Provider registration
# ---------------------------------------------------------------------------


class TestProviderRegistration:
    """Importing the module registers 'semantic_scholar' in the SearchRegistry."""

    def setup_method(self):
        self._original_providers = dict(_PROVIDERS)

    def teardown_method(self):
        _PROVIDERS.clear()
        _PROVIDERS.update(self._original_providers)

    def test_import_registers_provider(self):
        import core.search.semantic_scholar  # noqa: F401

        assert "semantic_scholar" in SearchRegistry.list_providers()

    def test_registry_creates_instance(self):
        import core.search.semantic_scholar  # noqa: F401
        from core.search.semantic_scholar import SemanticScholarProvider

        provider = SearchRegistry.create("semantic_scholar")
        assert isinstance(provider, SemanticScholarProvider)

    def test_provider_name_attribute(self):
        from core.search.semantic_scholar import SemanticScholarProvider

        provider = SemanticScholarProvider()
        assert provider.provider_name == "semantic_scholar"


# ---------------------------------------------------------------------------
# Keyword search — happy path
# ---------------------------------------------------------------------------


class TestKeywordSearch:
    @pytest.fixture
    def provider(self):
        from core.search.semantic_scholar import SemanticScholarProvider

        return SemanticScholarProvider()

    def test_keyword_search_returns_results(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="deep learning patent classification")
            response = provider.search(query)

        assert isinstance(response, SearchResponse)
        assert response.provider == "semantic_scholar"
        assert len(response.results) == 1
        assert response.error is None

    def test_results_have_npl_prefix(self, provider):
        """All patent_id values must be prefixed with 'NPL-'."""
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="deep learning")
            response = provider.search(query)

        assert response.results[0].patent_id.startswith("NPL-")
        assert "abc123def456" in response.results[0].patent_id

    def test_abstract_from_tldr_field(self, provider):
        """When tldr is present, use its text as abstract."""
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="deep learning")
            response = provider.search(query)

        result = response.results[0]
        assert result.abstract == "A deep learning method for patent classification."

    def test_abstract_fallback_to_abstract_field(self, provider):
        """When tldr is absent, fall back to abstract field."""
        paper_no_tldr = {
            "paperId": "xyz789",
            "title": "Some Paper",
            "abstract": "Full abstract text here.",
        }
        body = {"data": [paper_no_tldr], "total": 1}
        mock_resp = _make_mock_response(200, body)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="some paper")
            response = provider.search(query)

        assert response.results[0].abstract == "Full abstract text here."

    def test_search_strategy_is_npl(self, provider):
        """Results must have search_strategy set to 'npl'."""
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="deep learning")
            response = provider.search(query)

        # strategy field on SearchResult is a SearchStrategy enum
        assert response.results[0].strategy.value == "npl"

    def test_provider_field_is_semantic_scholar(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.results[0].provider == "semantic_scholar"


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------


class TestEmptyResults:
    @pytest.fixture
    def provider(self):
        from core.search.semantic_scholar import SemanticScholarProvider

        return SemanticScholarProvider()

    def test_empty_data_returns_empty_list(self, provider):
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="xyzzy_nonexistent_42")
            response = provider.search(query)

        assert response.results == []
        assert response.error is None

    def test_missing_data_key_treated_as_empty(self, provider):
        mock_resp = _make_mock_response(200, {})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.results == []
        assert response.error is None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.fixture
    def provider(self):
        from core.search.semantic_scholar import SemanticScholarProvider

        return SemanticScholarProvider()

    def test_429_rate_limit_returns_error_response(self, provider):
        mock_resp = _make_mock_response(429, {"error": "Too Many Requests"})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.results == []
        assert response.error is not None
        assert "429" in response.error or "rate" in response.error.lower()

    def test_timeout_returns_error_response(self, provider):
        mock_client = MagicMock()
        mock_client.get = MagicMock(
            side_effect=httpx.TimeoutException("timed out", request=MagicMock())
        )
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.results == []
        assert response.error is not None
        assert "timeout" in response.error.lower() or "timed" in response.error.lower()

    def test_connection_error_returns_error_response(self, provider):
        mock_client = MagicMock()
        mock_client.get = MagicMock(
            side_effect=httpx.ConnectError("connection refused")
        )
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.results == []
        assert response.error is not None

    def test_error_response_has_correct_provider(self, provider):
        mock_resp = _make_mock_response(500, {})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.provider == "semantic_scholar"

    def test_duration_ms_present_on_error(self, provider):
        mock_resp = _make_mock_response(500, {})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.duration_ms >= 0


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.fixture
    def provider(self):
        from core.search.semantic_scholar import SemanticScholarProvider

        return SemanticScholarProvider()

    def test_health_check_success(self, provider):
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            result = provider.health_check()

        assert result is True

    def test_health_check_failure_on_non_200(self, provider):
        mock_resp = _make_mock_response(429, {"error": "Rate limited"})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            result = provider.health_check()

        assert result is False

    def test_health_check_failure_on_network_error(self, provider):
        mock_client = MagicMock()
        mock_client.get = MagicMock(
            side_effect=httpx.RequestError("unreachable")
        )
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("httpx.Client", return_value=mock_client):
            result = provider.health_check()

        assert result is False


# ---------------------------------------------------------------------------
# Registry get_enabled with semantic_scholar flag
# ---------------------------------------------------------------------------


class TestGetEnabledSemanticScholar:
    def setup_method(self):
        self._original_providers = dict(_PROVIDERS)

    def teardown_method(self):
        _PROVIDERS.clear()
        _PROVIDERS.update(self._original_providers)

    def test_semantic_scholar_disabled_by_default(self):
        import core.search.semantic_scholar  # noqa: F401

        # Only register semantic_scholar for this test (clear others)
        _PROVIDERS.clear()
        _PROVIDERS["semantic_scholar"] = _PROVIDERS.get(
            "semantic_scholar",
        ) or __import__(
            "core.search.semantic_scholar", fromlist=["SemanticScholarProvider"]
        ).SemanticScholarProvider

        instances = SearchRegistry.get_enabled(
            patentsview_enabled=False,
            uspto_odp_enabled=False,
        )
        assert not any(p.provider_name == "semantic_scholar" for p in instances)

    def test_semantic_scholar_enabled_when_flagged(self):
        import core.search.semantic_scholar  # noqa: F401
        from core.search.semantic_scholar import SemanticScholarProvider

        _PROVIDERS.clear()
        _PROVIDERS["semantic_scholar"] = SemanticScholarProvider

        instances = SearchRegistry.get_enabled(
            patentsview_enabled=False,
            uspto_odp_enabled=False,
            semantic_scholar_enabled=True,
        )
        assert any(p.provider_name == "semantic_scholar" for p in instances)
