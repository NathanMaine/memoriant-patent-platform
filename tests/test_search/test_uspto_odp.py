"""Tests for the USPTO Open Data Portal search provider.

Written before implementation (TDD). All tests mock httpx.Client
to avoid real network calls.

API: GET https://developer.uspto.gov/ibd-api/v1/application/grants
Params: searchText, start, rows, largeTextSearchFlag
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from core.search.base import SearchQuery, SearchResponse
from core.search.registry import SearchRegistry, _PROVIDERS, register_provider


# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

SAMPLE_PATENT = {
    "patentNumber": "11234567",
    "patentTitle": "WIRELESS POWER TRANSFER SYSTEM",
    "patentAbstract": "A system for wirelessly transferring power.",
    "grantDate": "2023-05-15",
    "inventorName": ["Smith, John"],
    "assigneeEntityName": ["MedTech Inc"],
}

SAMPLE_RESPONSE = {
    "results": [SAMPLE_PATENT],
    "totalCount": 234,
}

EMPTY_RESPONSE = {
    "results": [],
    "totalCount": 0,
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


def test_uspto_odp_module_importable():
    """The module must import without errors."""
    import core.search.uspto_odp  # noqa: F401


# ---------------------------------------------------------------------------
# Provider self-registration
# ---------------------------------------------------------------------------


class TestProviderRegistration:
    """Importing the module registers 'uspto_odp' in the SearchRegistry."""

    def setup_method(self):
        self._original_providers = dict(_PROVIDERS)

    def teardown_method(self):
        _PROVIDERS.clear()
        _PROVIDERS.update(self._original_providers)

    def test_import_registers_provider(self):
        import core.search.uspto_odp  # noqa: F401

        assert "uspto_odp" in SearchRegistry.list_providers()

    def test_registry_creates_uspto_odp_instance(self):
        import core.search.uspto_odp  # noqa: F401
        from core.search.uspto_odp import USPTOODPProvider

        provider = SearchRegistry.create("uspto_odp")
        assert isinstance(provider, USPTOODPProvider)

    def test_provider_name_attribute(self):
        import core.search.uspto_odp  # noqa: F401
        from core.search.uspto_odp import USPTOODPProvider

        provider = USPTOODPProvider()
        assert provider.provider_name == "uspto_odp"


# ---------------------------------------------------------------------------
# Keyword search — happy path
# ---------------------------------------------------------------------------


class TestKeywordSearch:
    @pytest.fixture
    def provider(self):
        from core.search.uspto_odp import USPTOODPProvider

        return USPTOODPProvider()

    def test_keyword_search_returns_results(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="wireless power transfer")
            response = provider.search(query)

        assert isinstance(response, SearchResponse)
        assert response.provider == "uspto_odp"
        assert len(response.results) == 1
        assert response.results[0].patent_id == "11234567"
        assert response.results[0].title == "WIRELESS POWER TRANSFER SYSTEM"
        assert response.total_hits == 234
        assert response.error is None

    def test_keyword_search_sends_searchtext_param(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="wireless power")
            provider.search(query)

        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params") or (
            call_args.args[1] if len(call_args.args) > 1 else {}
        )
        assert "searchText" in params
        assert "wireless power" in params["searchText"]

    def test_keyword_search_sends_rows_param(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="battery", max_results=25)
            provider.search(query)

        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params") or {}
        assert "rows" in params
        assert params["rows"] == 25

    def test_keyword_search_sends_start_param(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="battery")
            provider.search(query)

        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params") or {}
        assert "start" in params

    def test_keyword_search_calls_correct_endpoint(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            provider.search(query)

        get_call = mock_client.get.call_args
        url = get_call.args[0] if get_call.args else get_call.kwargs.get("url", "")
        assert "developer.uspto.gov" in url
        assert "grants" in url


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------


class TestEmptyResults:
    @pytest.fixture
    def provider(self):
        from core.search.uspto_odp import USPTOODPProvider

        return USPTOODPProvider()

    def test_empty_results_returns_zero_hits(self, provider):
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="xyzzy_nonexistent_term_42")
            response = provider.search(query)

        assert response.results == []
        assert response.total_hits == 0
        assert response.error is None

    def test_missing_results_key_treated_as_empty(self, provider):
        """If the response body lacks 'results', provider returns empty list."""
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
        from core.search.uspto_odp import USPTOODPProvider

        return USPTOODPProvider()

    def test_400_returns_error_response(self, provider):
        mock_resp = _make_mock_response(400, {"error": "Bad Request"})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.results == []
        assert response.error is not None
        assert "400" in response.error

    def test_500_returns_error_response(self, provider):
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

    def test_generic_request_error_returns_error_response(self, provider):
        mock_client = MagicMock()
        mock_client.get = MagicMock(
            side_effect=httpx.RequestError("unexpected network failure")
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

        assert response.provider == "uspto_odp"

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
        from core.search.uspto_odp import USPTOODPProvider

        return USPTOODPProvider()

    def test_health_check_success(self, provider):
        mock_resp = _make_mock_response(200, {"results": [], "totalCount": 0})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            result = provider.health_check()

        assert result is True

    def test_health_check_failure_on_500(self, provider):
        mock_resp = _make_mock_response(500, {"error": "Server Error"})
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

    def test_health_check_uses_minimal_query(self, provider):
        """Health check should make a GET request with minimal parameters."""
        mock_resp = _make_mock_response(200, {"results": [], "totalCount": 0})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            provider.health_check()

        assert mock_client.get.called


# ---------------------------------------------------------------------------
# Response parsing details
# ---------------------------------------------------------------------------


class TestResponseParsing:
    @pytest.fixture
    def provider(self):
        from core.search.uspto_odp import USPTOODPProvider

        return USPTOODPProvider()

    def test_parsed_result_fields(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="wireless power")
            response = provider.search(query)

        result = response.results[0]
        assert result.patent_id == "11234567"
        assert result.title == "WIRELESS POWER TRANSFER SYSTEM"
        assert result.abstract == "A system for wirelessly transferring power."
        assert result.provider == "uspto_odp"
        assert result.strategy is not None

    def test_parsed_result_with_grant_date(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="wireless power")
            response = provider.search(query)

        result = response.results[0]
        assert str(result.patent_date) == "2023-05-15"

    def test_patent_with_no_abstract_parsed_as_none(self, provider):
        patent_no_abstract = {
            "patentNumber": "9999999",
            "patentTitle": "MINIMAL PATENT",
            "grantDate": "2021-01-01",
        }
        mock_resp = _make_mock_response(200, {"results": [patent_no_abstract], "totalCount": 1})
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="minimal")
            response = provider.search(query)

        result = response.results[0]
        assert result.abstract is None
        assert result.inventors == []
        assert result.assignees == []

    def test_duration_ms_is_non_negative(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.duration_ms >= 0

    def test_multiple_patents_parsed(self, provider):
        second_patent = {
            **SAMPLE_PATENT,
            "patentNumber": "99999999",
            "patentTitle": "SECOND PATENT",
        }
        body = {"results": [SAMPLE_PATENT, second_patent], "totalCount": 2}
        mock_resp = _make_mock_response(200, body)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="wireless")
            response = provider.search(query)

        assert len(response.results) == 2

    def test_total_hits_populated_from_response(self, provider):
        body = {**SAMPLE_RESPONSE, "totalCount": 999}
        mock_resp = _make_mock_response(200, body)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        assert response.total_hits == 999

    def test_inventor_name_without_comma_parsed_correctly(self, provider):
        """Inventor names without a comma put the whole name in 'last'."""
        patent_no_comma_inventor = {
            "patentNumber": "7654321",
            "patentTitle": "NO COMMA PATENT",
            "inventorName": ["JohnSmith"],
        }
        mock_resp = _make_mock_response(
            200, {"results": [patent_no_comma_inventor], "totalCount": 1}
        )
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test")
            response = provider.search(query)

        inventor = response.results[0].inventors[0]
        assert inventor.last == "JohnSmith"
        assert inventor.first == ""

    def test_unknown_strategy_falls_back_to_keyword(self, provider):
        """_primary_strategy returns KEYWORD when no known strategy is present."""
        from core.models.patent import SearchStrategy

        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_sync_client(mock_resp)

        with patch("httpx.Client", return_value=mock_client):
            query = SearchQuery(query="test", strategies=["boolean"])
            response = provider.search(query)

        assert response.results[0].strategy == SearchStrategy.KEYWORD
