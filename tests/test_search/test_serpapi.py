"""Tests for the SerpAPI Google Patents search provider.

Written before implementation (TDD). All tests mock httpx.Client
to avoid real network calls.

API: GET https://serpapi.com/search?engine=google_patents&q=...&api_key=...

This is a PAID, opt-in provider. The constructor requires a non-empty api_key.
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

SAMPLE_ORGANIC_RESULT = {
    "patent_id": "US11234567B2",
    "title": "WIRELESS POWER TRANSFER SYSTEM",
    "snippet": "A system for wirelessly transferring power.",
    "priority_date": "2023-05-15",
    "inventor": "John Smith",
    "assignee": "MedTech Inc",
    "pdf": "https://patentimages.storage.googleapis.com/US11234567B2.pdf",
}

SAMPLE_RESPONSE = {
    "organic_results": [SAMPLE_ORGANIC_RESULT],
    "search_information": {"total_results": 234},
}

EMPTY_RESPONSE: dict = {
    "organic_results": [],
    "search_information": {"total_results": 0},
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
# Import guard — provider must be importable
# ---------------------------------------------------------------------------


def test_serpapi_module_importable():
    """The module must import without errors."""
    import core.search.serpapi  # noqa: F401


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    """SerpAPIProvider requires a non-empty api_key."""

    def test_requires_api_key(self):
        """Instantiating without an api_key raises ValueError."""
        from core.search.serpapi import SerpAPIProvider

        with pytest.raises((ValueError, TypeError)):
            SerpAPIProvider()

    def test_empty_string_api_key_raises_value_error(self):
        """An empty string api_key raises ValueError."""
        from core.search.serpapi import SerpAPIProvider

        with pytest.raises(ValueError, match="api_key"):
            SerpAPIProvider(api_key="")

    def test_none_api_key_raises_value_error(self):
        """None api_key raises ValueError."""
        from core.search.serpapi import SerpAPIProvider

        with pytest.raises(ValueError, match="api_key"):
            SerpAPIProvider(api_key=None)

    def test_valid_api_key_creates_instance(self):
        """A non-empty api_key creates a provider successfully."""
        from core.search.serpapi import SerpAPIProvider

        provider = SerpAPIProvider(api_key="test-serpapi-key")
        assert provider.provider_name == "serpapi"
        assert provider.api_key == "test-serpapi-key"


# ---------------------------------------------------------------------------
# Provider self-registration
# ---------------------------------------------------------------------------


class TestProviderRegistration:
    """Importing the module registers 'serpapi' in the SearchRegistry."""

    def setup_method(self):
        self._original_providers = dict(_PROVIDERS)

    def teardown_method(self):
        _PROVIDERS.clear()
        _PROVIDERS.update(self._original_providers)

    def test_import_registers_provider(self):
        import core.search.serpapi  # noqa: F401

        assert "serpapi" in SearchRegistry.list_providers()

    def test_registry_creates_serpapi_instance(self):
        import core.search.serpapi  # noqa: F401
        from core.search.serpapi import SerpAPIProvider

        provider = SearchRegistry.create("serpapi", api_key="test-key")
        assert isinstance(provider, SerpAPIProvider)

    def test_provider_name_attribute(self):
        from core.search.serpapi import SerpAPIProvider

        provider = SerpAPIProvider(api_key="test-key")
        assert provider.provider_name == "serpapi"


# ---------------------------------------------------------------------------
# Keyword search — happy path
# ---------------------------------------------------------------------------


class TestKeywordSearch:
    @pytest.fixture
    def provider(self):
        from core.search.serpapi import SerpAPIProvider

        return SerpAPIProvider(api_key="test-serpapi-key")

    def test_keyword_search_returns_results(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="wireless power transfer")
            response = provider.search(query)

        assert isinstance(response, SearchResponse)
        assert response.provider == "serpapi"
        assert len(response.results) == 1
        assert response.results[0].patent_id == "US11234567B2"
        assert response.results[0].title == "WIRELESS POWER TRANSFER SYSTEM"
        assert response.error is None

    def test_keyword_search_sends_correct_params(self, provider):
        """Request must include engine=google_patents, q, api_key, and num."""
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="wireless power", max_results=20)
            provider.search(query)

        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params") or {}
        assert params.get("engine") == "google_patents"
        assert "wireless power" in params.get("q", "")
        assert params.get("api_key") == "test-serpapi-key"
        assert params.get("num") == 20

    def test_keyword_search_calls_serpapi_endpoint(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            provider.search(query)

        get_call = mock_client.get.call_args
        url = get_call.args[0] if get_call.args else get_call.kwargs.get("url", "")
        assert "serpapi.com" in url

    def test_total_hits_populated_from_response(self, provider):
        body = {
            "organic_results": [SAMPLE_ORGANIC_RESULT],
            "search_information": {"total_results": 999},
        }
        mock_resp = _make_mock_response(200, body)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.total_hits == 999


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------


class TestEmptyResults:
    @pytest.fixture
    def provider(self):
        from core.search.serpapi import SerpAPIProvider

        return SerpAPIProvider(api_key="test-serpapi-key")

    def test_empty_organic_results_returns_empty_list(self, provider):
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="xyzzy_nonexistent_term_42")
            response = provider.search(query)

        assert response.results == []
        assert response.error is None

    def test_missing_organic_results_key_treated_as_empty(self, provider):
        """If response body lacks 'organic_results', return empty list."""
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
        from core.search.serpapi import SerpAPIProvider

        return SerpAPIProvider(api_key="test-serpapi-key")

    def test_401_invalid_key_returns_error_response(self, provider):
        mock_resp = _make_mock_response(401, {"error": "Invalid API key"})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.results == []
        assert response.error is not None
        assert "401" in response.error or "key" in response.error.lower() or "invalid" in response.error.lower()

    def test_429_rate_limit_returns_error_response(self, provider):
        mock_resp = _make_mock_response(429, {"error": "Too Many Requests"})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.results == []
        assert response.error is not None
        assert "429" in response.error or "rate" in response.error.lower() or "limit" in response.error.lower()

    def test_500_server_error_returns_error_response(self, provider):
        mock_resp = _make_mock_response(500, {"error": "Internal Server Error"})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.results == []
        assert response.error is not None
        assert "500" in response.error or "server" in response.error.lower()

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

        assert response.provider == "serpapi"

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
        from core.search.serpapi import SerpAPIProvider

        return SerpAPIProvider(api_key="test-serpapi-key")

    def test_health_check_success(self, provider):
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            result = provider.health_check()

        assert result is True

    def test_health_check_failure_on_401(self, provider):
        mock_resp = _make_mock_response(401, {"error": "Unauthorized"})
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

    def test_health_check_makes_get_request(self, provider):
        """Health check must make a GET request to the SerpAPI endpoint."""
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            provider.health_check()

        assert mock_client.get.called

    def test_health_check_sends_api_key(self, provider):
        """Health check must include the api_key in the request params."""
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            provider.health_check()

        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params") or {}
        assert params.get("api_key") == "test-serpapi-key"


# ---------------------------------------------------------------------------
# Response parsing details
# ---------------------------------------------------------------------------


class TestResponseParsing:
    @pytest.fixture
    def provider(self):
        from core.search.serpapi import SerpAPIProvider

        return SerpAPIProvider(api_key="test-serpapi-key")

    def test_parsed_result_fields(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="wireless power")
            response = provider.search(query)

        result = response.results[0]
        assert result.patent_id == "US11234567B2"
        assert result.title == "WIRELESS POWER TRANSFER SYSTEM"
        assert result.abstract == "A system for wirelessly transferring power."
        assert result.provider == "serpapi"
        assert result.strategy is not None

    def test_duration_ms_is_non_negative(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.duration_ms >= 0

    def test_multiple_results_parsed(self, provider):
        second_result = {**SAMPLE_ORGANIC_RESULT, "patent_id": "US99999999B2", "title": "SECOND PATENT"}
        body = {
            "organic_results": [SAMPLE_ORGANIC_RESULT, second_result],
            "search_information": {"total_results": 2},
        }
        mock_resp = _make_mock_response(200, body)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="wireless")
            response = provider.search(query)

        assert len(response.results) == 2

    def test_result_with_missing_snippet_has_none_abstract(self, provider):
        """A result without 'snippet' should produce abstract=None."""
        result_no_snippet = {
            "patent_id": "US9999999B1",
            "title": "MINIMAL PATENT",
        }
        body = {"organic_results": [result_no_snippet]}
        mock_resp = _make_mock_response(200, body)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="minimal")
            response = provider.search(query)

        result = response.results[0]
        assert result.abstract is None

    def test_unknown_strategy_falls_back_to_keyword(self, provider):
        """_primary_strategy returns KEYWORD when no known strategy is present."""
        from core.models.patent import SearchStrategy

        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test", strategies=["boolean"])
            response = provider.search(query)

        assert response.results[0].strategy == SearchStrategy.KEYWORD
