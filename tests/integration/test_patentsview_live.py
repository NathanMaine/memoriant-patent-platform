"""Live integration tests for the PatentsView search provider.

These tests make real HTTP requests to the PatentsView API and require
PATENTSVIEW_API_KEY to be set in the environment.  They are skipped
automatically when the key is absent.
"""
from __future__ import annotations

import os

import pytest

from tests.integration.conftest import skip_no_patentsview
from core.search.patentsview import PatentsViewProvider
from core.search.base import SearchQuery


def _provider() -> PatentsViewProvider:
    return PatentsViewProvider(
        provider_name="patentsview",
        api_key=os.environ.get("PATENTSVIEW_API_KEY", ""),
    )


@skip_no_patentsview
@pytest.mark.asyncio
async def test_keyword_search_returns_results():
    """A common keyword search should return at least one patent."""
    provider = _provider()
    query = SearchQuery(query="wireless communication", strategies=["keyword"], max_results=5)
    response = await provider.search(query)

    assert response.error is None, f"Unexpected error: {response.error}"
    assert len(response.results) > 0, "Expected at least one patent result"


@skip_no_patentsview
@pytest.mark.asyncio
async def test_keyword_search_result_fields():
    """Each result from a live search must have patent_id and title populated."""
    provider = _provider()
    query = SearchQuery(query="wireless communication", strategies=["keyword"], max_results=5)
    response = await provider.search(query)

    assert response.error is None
    for result in response.results:
        assert result.patent_id, "patent_id must be non-empty"
        assert result.title, "title must be non-empty"
        assert result.provider == "patentsview"


@skip_no_patentsview
@pytest.mark.asyncio
async def test_cpc_classification_search():
    """CPC classification search should return patents with the requested subsection."""
    provider = _provider()
    # H04W is Wireless Communication Networks
    query = SearchQuery(
        query="",
        strategies=["classification"],
        cpc_codes=["H04W"],
        max_results=5,
    )
    response = await provider.search(query)

    assert response.error is None, f"Unexpected error: {response.error}"
    assert len(response.results) > 0, "Expected CPC search to return results"


@skip_no_patentsview
@pytest.mark.asyncio
async def test_health_check_passes_with_valid_key():
    """health_check() should return True when the API key is valid."""
    provider = _provider()
    ok = await provider.health_check()
    assert ok is True, "health_check should return True with a valid API key"
