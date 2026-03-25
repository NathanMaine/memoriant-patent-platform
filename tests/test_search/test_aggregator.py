"""Tests for SearchAggregator — parallel execution and deduplication.

Written before implementation (TDD). All tests use in-process mock providers
to avoid any real network calls.
"""
from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from core.models.patent import SearchResult, SearchStrategy
from core.search.aggregator import AggregatedSearchResponse, SearchAggregator
from core.search.base import SearchProvider, SearchQuery, SearchResponse


# ---------------------------------------------------------------------------
# Helpers: lightweight mock providers
# ---------------------------------------------------------------------------

def _make_result(
    patent_id: str,
    relevance_score: float | None = None,
    patent_date: date | None = None,
    provider: str = "mock_a",
) -> SearchResult:
    """Build a minimal SearchResult for testing."""
    return SearchResult(
        patent_id=patent_id,
        title=f"Patent {patent_id}",
        relevance_score=relevance_score,
        patent_date=patent_date,
        provider=provider,
        strategy=SearchStrategy.KEYWORD,
    )


def _make_response(
    results: list[SearchResult],
    provider: str = "mock_a",
    duration_ms: int = 42,
    total_hits: int | None = None,
    error: str | None = None,
) -> SearchResponse:
    return SearchResponse(
        results=results,
        provider=provider,
        duration_ms=duration_ms,
        total_hits=total_hits if total_hits is not None else len(results),
        error=error,
    )


class MockProvider(SearchProvider):
    """Test double that returns a pre-configured SearchResponse."""

    provider_name: str = "mock_a"
    response: SearchResponse

    async def search(self, query: SearchQuery) -> SearchResponse:  # type: ignore[override]
        return self.response

    async def health_check(self) -> bool:  # type: ignore[override]
        return True


class RaisingProvider(SearchProvider):
    """Test double whose search() always raises an exception."""

    provider_name: str = "raiser"
    exc_message: str = "provider boom"

    async def search(self, query: SearchQuery) -> SearchResponse:  # type: ignore[override]
        raise RuntimeError(self.exc_message)

    async def health_check(self) -> bool:  # type: ignore[override]
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def query() -> SearchQuery:
    return SearchQuery(query="machine learning patent")


@pytest.fixture
def result_a1() -> SearchResult:
    return _make_result("US123", relevance_score=0.9, patent_date=date(2023, 1, 1), provider="mock_a")


@pytest.fixture
def result_a2() -> SearchResult:
    return _make_result("US456", relevance_score=0.7, patent_date=date(2022, 6, 15), provider="mock_a")


@pytest.fixture
def result_b1() -> SearchResult:
    """Same patent_id as result_a1 but lower relevance — should be deduplicated away."""
    return _make_result("US123", relevance_score=0.5, patent_date=date(2023, 1, 1), provider="mock_b")


@pytest.fixture
def result_b2() -> SearchResult:
    return _make_result("US789", relevance_score=0.8, patent_date=date(2021, 3, 20), provider="mock_b")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_providers_both_succeed_results_merged(query, result_a1, result_a2, result_b2):
    """When both providers succeed, all unique results appear in the response."""
    provider_a = MockProvider(
        provider_name="mock_a",
        response=_make_response([result_a1, result_a2], provider="mock_a"),
    )
    provider_b = MockProvider(
        provider_name="mock_b",
        response=_make_response([result_b2], provider="mock_b"),
    )
    aggregator = SearchAggregator(providers=[provider_a, provider_b])
    agg = await aggregator.search(query)

    assert isinstance(agg, AggregatedSearchResponse)
    patent_ids = {r.patent_id for r in agg.results}
    assert patent_ids == {"US123", "US456", "US789"}
    assert len(agg.provider_responses) == 2
    assert agg.errors == []


@pytest.mark.asyncio
async def test_deduplication_keeps_higher_relevance(query, result_a1, result_b1):
    """Same patent_id from two providers → the one with higher relevance_score wins."""
    # result_a1 has relevance 0.9, result_b1 has 0.5 — a1 should survive
    provider_a = MockProvider(
        provider_name="mock_a",
        response=_make_response([result_a1], provider="mock_a"),
    )
    provider_b = MockProvider(
        provider_name="mock_b",
        response=_make_response([result_b1], provider="mock_b"),
    )
    aggregator = SearchAggregator(providers=[provider_a, provider_b])
    agg = await aggregator.search(query)

    assert len(agg.results) == 1
    assert agg.results[0].patent_id == "US123"
    assert agg.results[0].relevance_score == pytest.approx(0.9)
    assert agg.results[0].provider == "mock_a"


@pytest.mark.asyncio
async def test_deduplication_keeps_higher_relevance_reverse_order(query, result_a1, result_b1):
    """Deduplication works regardless of which provider is listed first."""
    # result_b1 has 0.5, result_a1 has 0.9 — a1 still wins even though b is first
    provider_b = MockProvider(
        provider_name="mock_b",
        response=_make_response([result_b1], provider="mock_b"),
    )
    provider_a = MockProvider(
        provider_name="mock_a",
        response=_make_response([result_a1], provider="mock_a"),
    )
    aggregator = SearchAggregator(providers=[provider_b, provider_a])
    agg = await aggregator.search(query)

    assert len(agg.results) == 1
    assert agg.results[0].relevance_score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_one_provider_raises_other_still_returns(query, result_b2):
    """If one provider raises, the other provider's results are still returned."""
    raiser = RaisingProvider(provider_name="raiser", exc_message="network failure")
    provider_b = MockProvider(
        provider_name="mock_b",
        response=_make_response([result_b2], provider="mock_b"),
    )
    aggregator = SearchAggregator(providers=[raiser, provider_b])
    agg = await aggregator.search(query)

    assert len(agg.results) == 1
    assert agg.results[0].patent_id == "US789"
    assert len(agg.errors) == 1
    assert "network failure" in agg.errors[0]


@pytest.mark.asyncio
async def test_one_provider_returns_error_response_others_still_work(query, result_a1):
    """A provider that returns a SearchResponse with error set still contributes no results."""
    error_provider = MockProvider(
        provider_name="mock_err",
        response=_make_response([], provider="mock_err", error="API key invalid"),
    )
    good_provider = MockProvider(
        provider_name="mock_a",
        response=_make_response([result_a1], provider="mock_a"),
    )
    aggregator = SearchAggregator(providers=[error_provider, good_provider])
    agg = await aggregator.search(query)

    assert len(agg.results) == 1
    assert agg.results[0].patent_id == "US123"
    # Error from the provider response should be surfaced
    assert len(agg.errors) == 1
    assert "API key invalid" in agg.errors[0]


@pytest.mark.asyncio
async def test_both_providers_return_empty(query):
    """When all providers return empty results, response is empty but valid."""
    provider_a = MockProvider(
        provider_name="mock_a",
        response=_make_response([], provider="mock_a"),
    )
    provider_b = MockProvider(
        provider_name="mock_b",
        response=_make_response([], provider="mock_b"),
    )
    aggregator = SearchAggregator(providers=[provider_a, provider_b])
    agg = await aggregator.search(query)

    assert agg.results == []
    assert agg.total_hits == 0
    assert agg.errors == []
    assert len(agg.provider_responses) == 2


@pytest.mark.asyncio
async def test_single_provider_works_fine(query, result_a1, result_a2):
    """A single provider is a valid configuration."""
    provider_a = MockProvider(
        provider_name="mock_a",
        response=_make_response([result_a1, result_a2], provider="mock_a"),
    )
    aggregator = SearchAggregator(providers=[provider_a])
    agg = await aggregator.search(query)

    assert len(agg.results) == 2
    assert len(agg.provider_responses) == 1


@pytest.mark.asyncio
async def test_zero_providers_returns_empty(query):
    """An aggregator with no providers returns an empty valid response."""
    aggregator = SearchAggregator(providers=[])
    agg = await aggregator.search(query)

    assert agg.results == []
    assert agg.total_hits == 0
    assert agg.errors == []
    assert agg.provider_responses == []


@pytest.mark.asyncio
async def test_sort_order_by_relevance_desc(query):
    """Results are sorted by relevance_score descending."""
    low = _make_result("US001", relevance_score=0.3, patent_date=date(2023, 1, 1))
    high = _make_result("US002", relevance_score=0.95, patent_date=date(2020, 6, 1))
    mid = _make_result("US003", relevance_score=0.6, patent_date=date(2022, 3, 1))

    provider = MockProvider(
        provider_name="mock_a",
        response=_make_response([low, high, mid]),
    )
    aggregator = SearchAggregator(providers=[provider])
    agg = await aggregator.search(query)

    scores = [r.relevance_score for r in agg.results]
    assert scores == [0.95, 0.6, 0.3]


@pytest.mark.asyncio
async def test_sort_order_by_date_desc_when_relevance_equal(query):
    """When relevance scores are equal, results are sorted by patent_date descending."""
    older = _make_result("US010", relevance_score=0.5, patent_date=date(2019, 1, 1))
    newer = _make_result("US011", relevance_score=0.5, patent_date=date(2023, 12, 31))
    mid = _make_result("US012", relevance_score=0.5, patent_date=date(2021, 6, 15))

    provider = MockProvider(
        provider_name="mock_a",
        response=_make_response([older, newer, mid]),
    )
    aggregator = SearchAggregator(providers=[provider])
    agg = await aggregator.search(query)

    patent_ids = [r.patent_id for r in agg.results]
    assert patent_ids == ["US011", "US012", "US010"]


@pytest.mark.asyncio
async def test_sort_none_relevance_goes_last(query):
    """Results with no relevance_score sort after those with a score."""
    with_score = _make_result("US020", relevance_score=0.4, patent_date=date(2022, 1, 1))
    no_score = _make_result("US021", relevance_score=None, patent_date=date(2023, 1, 1))

    provider = MockProvider(
        provider_name="mock_a",
        response=_make_response([no_score, with_score]),
    )
    aggregator = SearchAggregator(providers=[provider])
    agg = await aggregator.search(query)

    assert agg.results[0].patent_id == "US020"
    assert agg.results[1].patent_id == "US021"


@pytest.mark.asyncio
async def test_duration_ms_is_tracked(query, result_a1):
    """AggregatedSearchResponse.duration_ms is a non-negative integer."""
    provider = MockProvider(
        provider_name="mock_a",
        response=_make_response([result_a1]),
    )
    aggregator = SearchAggregator(providers=[provider])
    agg = await aggregator.search(query)

    assert isinstance(agg.duration_ms, int)
    assert agg.duration_ms >= 0


@pytest.mark.asyncio
async def test_total_hits_is_sum_of_unique_results(query, result_a1, result_a2, result_b2):
    """total_hits reflects the count of deduplicated results returned."""
    provider_a = MockProvider(
        provider_name="mock_a",
        response=_make_response([result_a1, result_a2], provider="mock_a"),
    )
    provider_b = MockProvider(
        provider_name="mock_b",
        response=_make_response([result_b2], provider="mock_b"),
    )
    aggregator = SearchAggregator(providers=[provider_a, provider_b])
    agg = await aggregator.search(query)

    assert agg.total_hits == 3  # US123, US456, US789


@pytest.mark.asyncio
async def test_provider_responses_contain_per_provider_detail(query, result_a1, result_b2):
    """provider_responses list gives per-provider SearchResponse objects."""
    provider_a = MockProvider(
        provider_name="mock_a",
        response=_make_response([result_a1], provider="mock_a", duration_ms=10),
    )
    provider_b = MockProvider(
        provider_name="mock_b",
        response=_make_response([result_b2], provider="mock_b", duration_ms=20),
    )
    aggregator = SearchAggregator(providers=[provider_a, provider_b])
    agg = await aggregator.search(query)

    providers_seen = {r.provider for r in agg.provider_responses}
    assert providers_seen == {"mock_a", "mock_b"}


@pytest.mark.asyncio
async def test_both_providers_raise_returns_empty_with_two_errors(query):
    """When every provider raises, results are empty and all errors are collected."""
    raiser_a = RaisingProvider(provider_name="raiser_a", exc_message="error A")
    raiser_b = RaisingProvider(provider_name="raiser_b", exc_message="error B")
    aggregator = SearchAggregator(providers=[raiser_a, raiser_b])
    agg = await aggregator.search(query)

    assert agg.results == []
    assert len(agg.errors) == 2


@pytest.mark.asyncio
async def test_aggregated_response_is_pydantic_model(query, result_a1):
    """AggregatedSearchResponse is a proper Pydantic model."""
    provider = MockProvider(
        provider_name="mock_a",
        response=_make_response([result_a1]),
    )
    aggregator = SearchAggregator(providers=[provider])
    agg = await aggregator.search(query)

    # Pydantic models support .model_dump()
    dumped = agg.model_dump()
    assert "results" in dumped
    assert "total_hits" in dumped
    assert "provider_responses" in dumped
    assert "duration_ms" in dumped
    assert "errors" in dumped
