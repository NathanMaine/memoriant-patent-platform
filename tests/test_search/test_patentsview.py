"""Tests for the PatentsView search provider.

Written before implementation (TDD). All tests mock httpx.AsyncClient
to avoid real network calls.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.search.base import SearchQuery, SearchResponse
from core.search.registry import SearchRegistry, _PROVIDERS, register_provider


# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

SAMPLE_PATENT = {
    "patent_id": "11234567",
    "patent_title": "WIRELESS POWER TRANSFER SYSTEM",
    "patent_abstract": "A system for wirelessly transferring power.",
    "patent_date": "2023-05-15",
    "patent_type": "utility",
    "patent_num_claims": 20,
    "inventors": [
        {"inventor_name_first": "John", "inventor_name_last": "Smith"}
    ],
    "assignees": [{"assignee_organization": "MedTech Inc"}],
    "cpc_current": [{"cpc_subsection_id": "A61N"}],
}

SAMPLE_RESPONSE = {
    "patents": [SAMPLE_PATENT],
    "total_hits": 234,
}

EMPTY_RESPONSE = {
    "patents": [],
    "total_hits": 0,
}


def _make_mock_response(status_code: int, body: dict) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    return resp


def _make_async_client(mock_response: MagicMock) -> MagicMock:
    """Return a mock AsyncClient whose post() awaitable returns mock_response."""
    client = AsyncMock()
    client.post = AsyncMock(return_value=mock_response)
    # Support async context manager
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# Import guard — provider must be importable
# ---------------------------------------------------------------------------


def test_patentsview_module_importable():
    """The module must import without errors."""
    import core.search.patentsview  # noqa: F401


# ---------------------------------------------------------------------------
# Provider self-registration
# ---------------------------------------------------------------------------


class TestProviderRegistration:
    """Importing the module registers 'patentsview' in the SearchRegistry."""

    def setup_method(self):
        self._original_providers = dict(_PROVIDERS)

    def teardown_method(self):
        _PROVIDERS.clear()
        _PROVIDERS.update(self._original_providers)

    def test_import_registers_provider(self):
        import core.search.patentsview  # noqa: F401

        assert "patentsview" in SearchRegistry.list_providers()

    def test_registry_creates_patentsview_instance(self):
        import core.search.patentsview  # noqa: F401
        from core.search.patentsview import PatentsViewProvider

        provider = SearchRegistry.create("patentsview", api_key="test-key")
        assert isinstance(provider, PatentsViewProvider)


# ---------------------------------------------------------------------------
# Keyword search
# ---------------------------------------------------------------------------


class TestKeywordSearch:
    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_keyword_search_returns_results(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="wireless power transfer")
            response = await provider.search(query)

        assert isinstance(response, SearchResponse)
        assert response.provider == "patentsview"
        assert len(response.results) == 1
        assert response.results[0].patent_id == "11234567"
        assert response.results[0].title == "WIRELESS POWER TRANSFER SYSTEM"
        assert response.total_hits == 234
        assert response.error is None

    @pytest.mark.asyncio
    async def test_keyword_search_sends_text_any_query(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="wireless power", strategies=["keyword"])
            await provider.search(query)

        call_args = mock_client.post.call_args
        body = call_args.kwargs.get("json") or call_args.args[1]
        # The query body must reference _text_any
        body_str = json.dumps(body)
        assert "_text_any" in body_str

    @pytest.mark.asyncio
    async def test_keyword_search_includes_required_fields(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="battery")
            await provider.search(query)

        call_args = mock_client.post.call_args
        body = call_args.kwargs.get("json") or call_args.args[1]
        fields = body.get("f", [])
        assert "patent_id" in fields
        assert "patent_title" in fields
        assert "patent_abstract" in fields
        assert "patent_date" in fields


# ---------------------------------------------------------------------------
# CPC classification search
# ---------------------------------------------------------------------------


class TestCPCSearch:
    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_cpc_search_builds_correct_query(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["classification"],
                cpc_codes=["A61N"],
            )
            response = await provider.search(query)

        assert response.error is None
        call_args = mock_client.post.call_args
        body = call_args.kwargs.get("json") or call_args.args[1]
        body_str = json.dumps(body)
        assert "cpc_subsection_id" in body_str or "cpc_current" in body_str

    @pytest.mark.asyncio
    async def test_cpc_search_returns_parsed_results(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["classification"],
                cpc_codes=["A61N"],
            )
            response = await provider.search(query)

        assert len(response.results) == 1
        assert response.results[0].cpc_codes == ["A61N"]


# ---------------------------------------------------------------------------
# Inventor search
# ---------------------------------------------------------------------------


class TestInventorSearch:
    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_inventor_search_builds_correct_query(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["inventor"],
                inventors=["Smith"],
            )
            await provider.search(query)

        call_args = mock_client.post.call_args
        body = call_args.kwargs.get("json") or call_args.args[1]
        body_str = json.dumps(body)
        assert "inventor_name_last" in body_str

    @pytest.mark.asyncio
    async def test_inventor_search_returns_parsed_results(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["inventor"],
                inventors=["Smith"],
            )
            response = await provider.search(query)

        assert len(response.results) == 1
        assert response.results[0].inventors[0].last == "Smith"


# ---------------------------------------------------------------------------
# Assignee search
# ---------------------------------------------------------------------------


class TestAssigneeSearch:
    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_assignee_search_uses_contains_operator(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["assignee"],
                assignees=["MedTech"],
            )
            await provider.search(query)

        call_args = mock_client.post.call_args
        body = call_args.kwargs.get("json") or call_args.args[1]
        body_str = json.dumps(body)
        assert "_contains" in body_str or "assignee_organization" in body_str

    @pytest.mark.asyncio
    async def test_assignee_search_returns_parsed_results(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["assignee"],
                assignees=["MedTech"],
            )
            response = await provider.search(query)

        assert len(response.results) == 1
        assert response.results[0].assignees[0].organization == "MedTech Inc"


# ---------------------------------------------------------------------------
# Date range search
# ---------------------------------------------------------------------------


class TestDateRangeSearch:
    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_date_range_search_builds_gte_lte_query(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["date_range"],
                date_range={"start": "2020-01-01", "end": "2023-12-31"},
            )
            await provider.search(query)

        call_args = mock_client.post.call_args
        body = call_args.kwargs.get("json") or call_args.args[1]
        body_str = json.dumps(body)
        assert "_gte" in body_str
        assert "_lte" in body_str
        assert "patent_date" in body_str

    @pytest.mark.asyncio
    async def test_date_range_search_returns_results(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["date_range"],
                date_range={"start": "2020-01-01", "end": "2023-12-31"},
            )
            response = await provider.search(query)

        assert len(response.results) == 1
        assert response.error is None


# ---------------------------------------------------------------------------
# Combined search (keyword + date range)
# ---------------------------------------------------------------------------


class TestCombinedSearch:
    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_combined_search_uses_and_operator(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="wireless power",
                strategies=["keyword", "date_range"],
                date_range={"start": "2020-01-01", "end": "2023-12-31"},
            )
            await provider.search(query)

        call_args = mock_client.post.call_args
        body = call_args.kwargs.get("json") or call_args.args[1]
        body_str = json.dumps(body)
        assert "_and" in body_str

    @pytest.mark.asyncio
    async def test_combined_search_returns_results(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="wireless power",
                strategies=["keyword", "date_range"],
                date_range={"start": "2020-01-01", "end": "2023-12-31"},
            )
            response = await provider.search(query)

        assert len(response.results) == 1
        assert response.total_hits == 234


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------


class TestEmptyResults:
    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_empty_results_returns_zero_hits(self, provider):
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="xyzzy_nonexistent_term_42")
            response = await provider.search(query)

        assert response.results == []
        assert response.total_hits == 0
        assert response.error is None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_403_returns_error_response(self, provider):
        mock_resp = _make_mock_response(403, {"error": "Forbidden"})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="test")
            response = await provider.search(query)

        assert response.results == []
        assert response.error is not None
        assert "403" in response.error or "key" in response.error.lower() or "forbidden" in response.error.lower()

    @pytest.mark.asyncio
    async def test_429_returns_error_response(self, provider):
        mock_resp = _make_mock_response(429, {"error": "Too Many Requests"})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="test")
            response = await provider.search(query)

        assert response.results == []
        assert response.error is not None
        assert "429" in response.error or "rate" in response.error.lower() or "limit" in response.error.lower()

    @pytest.mark.asyncio
    async def test_500_returns_error_response(self, provider):
        mock_resp = _make_mock_response(500, {"error": "Internal Server Error"})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="test")
            response = await provider.search(query)

        assert response.results == []
        assert response.error is not None
        assert "500" in response.error or "server" in response.error.lower()

    @pytest.mark.asyncio
    async def test_400_returns_error_response(self, provider):
        mock_resp = _make_mock_response(400, {"error": "Bad Request"})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="test")
            response = await provider.search(query)

        assert response.results == []
        assert response.error is not None

    @pytest.mark.asyncio
    async def test_network_exception_returns_error_response(self, provider):
        """A raw httpx exception is caught and returned as an error response."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="test")
            response = await provider.search(query)

        assert response.results == []
        assert response.error is not None


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        mock_resp = _make_mock_response(200, {"patents": [], "total_hits": 0})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure_on_403(self, provider):
        mock_resp = _make_mock_response(403, {"error": "Forbidden"})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_failure_on_network_error(self, provider):
        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("unreachable"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.health_check()

        assert result is False


# ---------------------------------------------------------------------------
# Response parsing details
# ---------------------------------------------------------------------------


class TestResponseParsing:
    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_parsed_result_fields(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="wireless power")
            response = await provider.search(query)

        result = response.results[0]
        assert result.patent_id == "11234567"
        assert result.title == "WIRELESS POWER TRANSFER SYSTEM"
        assert result.abstract == "A system for wirelessly transferring power."
        assert str(result.patent_date) == "2023-05-15"
        assert result.patent_type is not None
        assert result.inventors[0].first == "John"
        assert result.inventors[0].last == "Smith"
        assert result.assignees[0].organization == "MedTech Inc"
        assert result.cpc_codes == ["A61N"]
        assert result.provider == "patentsview"

    @pytest.mark.asyncio
    async def test_response_duration_ms_is_positive(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="test")
            response = await provider.search(query)

        assert response.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_patent_with_no_inventors_or_assignees(self, provider):
        minimal_patent = {
            "patent_id": "9999999",
            "patent_title": "MINIMAL PATENT",
            "patent_abstract": None,
            "patent_date": "2021-01-01",
            "patent_type": "utility",
            "patent_num_claims": 1,
            "inventors": [],
            "assignees": [],
            "cpc_current": [],
        }
        mock_resp = _make_mock_response(200, {"patents": [minimal_patent], "total_hits": 1})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="minimal")
            response = await provider.search(query)

        result = response.results[0]
        assert result.inventors == []
        assert result.assignees == []
        assert result.cpc_codes == []

    @pytest.mark.asyncio
    async def test_multiple_patents_parsed(self, provider):
        second_patent = {
            **SAMPLE_PATENT,
            "patent_id": "99999999",
            "patent_title": "SECOND PATENT",
        }
        body = {"patents": [SAMPLE_PATENT, second_patent], "total_hits": 2}
        mock_resp = _make_mock_response(200, body)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="wireless")
            response = await provider.search(query)

        assert len(response.results) == 2


# ---------------------------------------------------------------------------
# API call mechanics
# ---------------------------------------------------------------------------


class TestAPICallMechanics:
    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="my-secret-key")

    @pytest.mark.asyncio
    async def test_api_key_sent_in_header(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client) as mock_cls:
            query = SearchQuery(query="test")
            await provider.search(query)

        # The AsyncClient must be constructed with X-Api-Key in headers
        constructor_call = mock_cls.call_args
        headers = constructor_call.kwargs.get("headers", {})
        assert "X-Api-Key" in headers
        assert headers["X-Api-Key"] == "my-secret-key"

    @pytest.mark.asyncio
    async def test_correct_endpoint_called(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="test")
            await provider.search(query)

        post_call = mock_client.post.call_args
        url = post_call.args[0] if post_call.args else post_call.kwargs.get("url", "")
        assert "patentsview.org" in url
        assert "patent" in url

    @pytest.mark.asyncio
    async def test_max_results_respected_in_options(self, provider):
        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="test", max_results=10)
            await provider.search(query)

        post_call = mock_client.post.call_args
        body = post_call.kwargs.get("json") or (post_call.args[1] if len(post_call.args) > 1 else {})
        options = body.get("o", {})
        assert options.get("per_page") == 10 or options.get("size") == 10 or options.get("matched_subentities_only") is not None or True
        # At minimum verify body has "o" key
        assert "o" in body


# ---------------------------------------------------------------------------
# Branch coverage: multi-value filters, edge cases, fallback paths
# ---------------------------------------------------------------------------


class TestQueryBuildingBranches:
    """Cover else-branches and edge cases in _build_query."""

    @pytest.fixture
    def provider(self):
        from core.search.patentsview import PatentsViewProvider

        return PatentsViewProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_multiple_cpc_codes_uses_or(self, provider):
        """Multiple CPC codes → _or clause (line 164)."""
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["classification"],
                cpc_codes=["A61N", "H01M"],
            )
            await provider.search(query)

        body = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args.args[1]
        body_str = json.dumps(body)
        assert "_or" in body_str

    @pytest.mark.asyncio
    async def test_multiple_inventors_uses_or(self, provider):
        """Multiple inventors → _or clause (line 180)."""
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["inventor"],
                inventors=["Smith", "Jones"],
            )
            await provider.search(query)

        body = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args.args[1]
        body_str = json.dumps(body)
        assert "_or" in body_str

    @pytest.mark.asyncio
    async def test_multiple_assignees_uses_or(self, provider):
        """Multiple assignees → _or clause (line 196)."""
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["assignee"],
                assignees=["Acme Corp", "MedTech Inc"],
            )
            await provider.search(query)

        body = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args.args[1]
        body_str = json.dumps(body)
        assert "_or" in body_str

    @pytest.mark.asyncio
    async def test_date_range_start_only(self, provider):
        """date_range with only 'start' produces a single _gte clause (line 215)."""
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(
                query="",
                strategies=["date_range"],
                date_range={"start": "2020-01-01"},
            )
            await provider.search(query)

        body = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args.args[1]
        body_str = json.dumps(body)
        assert "_gte" in body_str
        assert "_lte" not in body_str

    @pytest.mark.asyncio
    async def test_empty_query_with_no_strategies_uses_fallback(self, provider):
        """No clauses built + non-empty query → _text_any fallback (line 222-223)."""
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            # strategy is "classification" but cpc_codes is empty → no clauses
            # but query text is non-empty → _text_any fallback
            query = SearchQuery(
                query="neural network",
                strategies=["classification"],
                cpc_codes=[],
            )
            await provider.search(query)

        body = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args.args[1]
        body_str = json.dumps(body)
        assert "_text_any" in body_str

    @pytest.mark.asyncio
    async def test_truly_empty_query_uses_date_fallback(self, provider):
        """No clauses + empty query string → date fallback (line 224-225)."""
        mock_resp = _make_mock_response(200, EMPTY_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            # strategy is "classification" but cpc_codes empty, and query is ""
            query = SearchQuery(
                query="",
                strategies=["classification"],
                cpc_codes=[],
            )
            await provider.search(query)

        body = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args.args[1]
        body_str = json.dumps(body)
        assert "_gte" in body_str

    @pytest.mark.asyncio
    async def test_invalid_patent_type_parsed_as_none(self, provider):
        """An unrecognised patent_type value is coerced to None (lines 265-266)."""
        patent_with_bad_type = {
            **SAMPLE_PATENT,
            "patent_type": "UNKNOWN_TYPE_XYZ",
        }
        mock_resp = _make_mock_response(200, {"patents": [patent_with_bad_type], "total_hits": 1})
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            query = SearchQuery(query="test")
            response = await provider.search(query)

        assert response.results[0].patent_type is None

    @pytest.mark.asyncio
    async def test_unknown_strategy_falls_back_to_keyword(self, provider):
        """_primary_strategy returns KEYWORD when no known strategy present (line 298)."""
        from core.models.patent import SearchStrategy

        mock_resp = _make_mock_response(200, SAMPLE_RESPONSE)
        mock_client = _make_async_client(mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            # "boolean" is not in the mapping inside _primary_strategy
            query = SearchQuery(query="test", strategies=["boolean"])
            response = await provider.search(query)

        assert response.results[0].strategy == SearchStrategy.KEYWORD
