"""SerpAPI Google Patents search provider.

Implements the SearchProvider interface against the SerpAPI Google Patents engine:
  GET https://serpapi.com/search?engine=google_patents&q=...&api_key=...

This is a PAID, opt-in provider. Users must explicitly supply an API key.
SerpAPI is NOT enabled by default in SearchRegistry.get_enabled().

Authentication:  api_key query parameter.
Rate limits:     Depend on the user's SerpAPI plan.
Documentation:   https://serpapi.com/google-patents-api
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from core.models.patent import Assignee, Inventor, SearchResult, SearchStrategy
from core.search.base import SearchProvider, SearchQuery, SearchResponse
from core.search.registry import register_provider

logger = structlog.get_logger(__name__)

_ENDPOINT = "https://serpapi.com/search"

_ERROR_MESSAGES: dict[int, str] = {
    401: "401 Invalid SerpAPI key or unauthorized",
    429: "429 Rate limit exceeded: slow down requests",
    500: "500 SerpAPI server error",
}


class SerpAPIProvider(SearchProvider):
    """Concrete SearchProvider for the SerpAPI Google Patents engine.

    This provider is PAID and opt-in.  Pass ``serpapi_enabled=True`` and
    ``api_key=<your_key>`` to ``SearchRegistry.get_enabled()`` to activate it.
    """

    provider_name: str = "serpapi"
    api_key: str

    def model_post_init(self, __context: Any) -> None:
        """Validate that api_key is non-empty after Pydantic initialisation."""
        if not self.api_key:
            raise ValueError("api_key is required for SerpAPIProvider and must not be empty")

    # -----------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------

    def search(self, query: SearchQuery) -> SearchResponse:
        """Execute a Google Patents search via SerpAPI and return a SearchResponse."""
        start_time = time.monotonic()
        log = logger.bind(provider=self.provider_name, query=query.query)

        params: dict[str, Any] = {
            "engine": "google_patents",
            "q": query.query,
            "api_key": self.api_key,
            "num": query.max_results,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                log.info("serpapi_api_call", endpoint=_ENDPOINT, query=query.query)
                resp = client.get(_ENDPOINT, params=params)
        except httpx.TimeoutException as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log.error("serpapi_timeout", error=str(exc), duration_ms=duration_ms)
            return SearchResponse(
                results=[],
                provider=self.provider_name,
                duration_ms=duration_ms,
                error=f"Timeout error: {exc}",
            )
        except httpx.RequestError as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log.error("serpapi_network_error", error=str(exc), duration_ms=duration_ms)
            return SearchResponse(
                results=[],
                provider=self.provider_name,
                duration_ms=duration_ms,
                error=f"Network error: {exc}",
            )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        log.info("serpapi_api_response", status=resp.status_code, duration_ms=duration_ms)

        if resp.status_code != 200:
            error_msg = _ERROR_MESSAGES.get(
                resp.status_code,
                f"{resp.status_code} Unexpected error from SerpAPI",
            )
            log.error("serpapi_api_error", status=resp.status_code, message=error_msg)
            return SearchResponse(
                results=[],
                provider=self.provider_name,
                duration_ms=duration_ms,
                error=error_msg,
            )

        data = resp.json()
        results = self._parse_results(data, query)
        search_info = data.get("search_information") or {}
        total_hits = search_info.get("total_results", len(results))

        log.info("serpapi_search_complete", results=len(results), total_hits=total_hits)
        return SearchResponse(
            results=results,
            provider=self.provider_name,
            duration_ms=duration_ms,
            total_hits=total_hits,
        )

    def health_check(self) -> bool:
        """Make a minimal query to verify the API key is valid and SerpAPI is reachable."""
        log = logger.bind(provider=self.provider_name)
        params: dict[str, Any] = {
            "engine": "google_patents",
            "q": "patent",
            "api_key": self.api_key,
            "num": 1,
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(_ENDPOINT, params=params)
                ok = resp.status_code == 200
                log.info("serpapi_health_check", status=resp.status_code, ok=ok)
                return ok
        except httpx.RequestError as exc:
            log.error("serpapi_health_check_failed", error=str(exc))
            return False

    # -----------------------------------------------------------------
    # Response parsing
    # -----------------------------------------------------------------

    def _parse_results(self, data: dict[str, Any], query: SearchQuery) -> list[SearchResult]:
        """Parse SerpAPI response JSON into SearchResult objects."""
        organic: list[dict[str, Any]] = data.get("organic_results") or []
        strategy = self._primary_strategy(query)
        results: list[SearchResult] = []

        for raw in organic:
            patent_id = raw.get("patent_id", "")
            title = raw.get("title", "")
            abstract = raw.get("snippet") or None

            # SerpAPI returns flat inventor/assignee strings; wrap into model objects
            inventor_str = raw.get("inventor")
            inventors: list[Inventor] = []
            if inventor_str:
                inventors = [Inventor(first="", last=inventor_str.strip())]

            assignee_str = raw.get("assignee")
            assignees: list[Assignee] = []
            if assignee_str:
                assignees = [Assignee(organization=assignee_str.strip())]

            patent_date = raw.get("priority_date") or raw.get("filing_date") or None

            results.append(
                SearchResult(
                    patent_id=patent_id,
                    title=title,
                    abstract=abstract,
                    patent_date=patent_date,
                    inventors=inventors,
                    assignees=assignees,
                    provider=self.provider_name,
                    strategy=strategy,
                )
            )

        return results

    @staticmethod
    def _primary_strategy(query: SearchQuery) -> SearchStrategy:
        """Derive the primary SearchStrategy enum value from a SearchQuery."""
        mapping = {
            "keyword": SearchStrategy.KEYWORD,
            "classification": SearchStrategy.CLASSIFICATION,
            "inventor": SearchStrategy.INVENTOR,
            "assignee": SearchStrategy.ASSIGNEE,
            "date_range": SearchStrategy.DATE_RANGE,
        }
        for s in query.strategies:
            if s in mapping:
                return mapping[s]
        return SearchStrategy.KEYWORD


# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------

register_provider("serpapi", SerpAPIProvider)
