"""USPTO Open Data Portal (ODP) search provider.

Implements the SearchProvider interface against the USPTO ODP REST API:
  GET https://developer.uspto.gov/ibd-api/v1/application/grants

Query parameters:
    searchText          Full-text search term(s).
    start               Zero-based result offset (pagination).
    rows                Number of results to return per request.
    largeTextSearchFlag Set to "Y" to enable large-text search mode.

No API key is required; the endpoint is publicly accessible.
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

_ENDPOINT = "https://developer.uspto.gov/ibd-api/v1/application/grants"

_ERROR_MESSAGES: dict[int, str] = {
    400: "400 Bad request: malformed query sent to USPTO ODP",
    500: "500 USPTO ODP server error",
}


class USPTOODPProvider(SearchProvider):
    """Concrete SearchProvider for the USPTO Open Data Portal API."""

    provider_name: str = "uspto_odp"

    # -----------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------

    def search(self, query: SearchQuery) -> SearchResponse:
        """Execute a patent grant search against USPTO ODP and return a SearchResponse."""
        start_time = time.monotonic()
        log = logger.bind(provider=self.provider_name, query=query.query)

        params: dict[str, Any] = {
            "searchText": query.query,
            "start": 0,
            "rows": query.max_results,
            "largeTextSearchFlag": "N",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                log.info("uspto_odp_api_call", endpoint=_ENDPOINT, params=params)
                resp = client.get(_ENDPOINT, params=params)
        except httpx.TimeoutException as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log.error("uspto_odp_timeout", error=str(exc), duration_ms=duration_ms)
            return SearchResponse(
                results=[],
                provider=self.provider_name,
                duration_ms=duration_ms,
                error=f"Timeout error: {exc}",
            )
        except httpx.RequestError as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log.error("uspto_odp_network_error", error=str(exc), duration_ms=duration_ms)
            return SearchResponse(
                results=[],
                provider=self.provider_name,
                duration_ms=duration_ms,
                error=f"Network error: {exc}",
            )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        log.info("uspto_odp_api_response", status=resp.status_code, duration_ms=duration_ms)

        if resp.status_code != 200:
            error_msg = _ERROR_MESSAGES.get(
                resp.status_code,
                f"{resp.status_code} Unexpected error from USPTO ODP",
            )
            log.error("uspto_odp_api_error", status=resp.status_code, message=error_msg)
            return SearchResponse(
                results=[],
                provider=self.provider_name,
                duration_ms=duration_ms,
                error=error_msg,
            )

        data = resp.json()
        results = self._parse_results(data, query)
        total_hits = data.get("totalCount", len(results))

        log.info("uspto_odp_search_complete", results=len(results), total_hits=total_hits)
        return SearchResponse(
            results=results,
            provider=self.provider_name,
            duration_ms=duration_ms,
            total_hits=total_hits,
        )

    def health_check(self) -> bool:
        """Make a minimal query to verify connectivity to the USPTO ODP API."""
        log = logger.bind(provider=self.provider_name)
        try:
            with httpx.Client(timeout=10.0) as client:
                params: dict[str, Any] = {
                    "searchText": "patent",
                    "start": 0,
                    "rows": 1,
                    "largeTextSearchFlag": "N",
                }
                resp = client.get(_ENDPOINT, params=params)
                ok = resp.status_code == 200
                log.info("uspto_odp_health_check", status=resp.status_code, ok=ok)
                return ok
        except httpx.RequestError as exc:
            log.error("uspto_odp_health_check_failed", error=str(exc))
            return False

    # -----------------------------------------------------------------
    # Response parsing
    # -----------------------------------------------------------------

    def _parse_results(self, data: dict[str, Any], query: SearchQuery) -> list[SearchResult]:
        """Parse USPTO ODP response JSON into SearchResult objects."""
        raw_grants: list[dict[str, Any]] = data.get("results") or []
        strategy = self._primary_strategy(query)
        results: list[SearchResult] = []

        for raw in raw_grants:
            inventors = self._parse_inventors(raw.get("inventorName") or [])
            assignees = self._parse_assignees(raw.get("assigneeEntityName") or [])

            results.append(
                SearchResult(
                    patent_id=raw.get("patentNumber", ""),
                    title=raw.get("patentTitle", ""),
                    abstract=raw.get("patentAbstract") or None,
                    patent_date=raw.get("grantDate") or None,
                    inventors=inventors,
                    assignees=assignees,
                    provider=self.provider_name,
                    strategy=strategy,
                )
            )

        return results

    @staticmethod
    def _parse_inventors(inventor_names: list[str]) -> list[Inventor]:
        """Parse inventor name strings (e.g. 'Smith, John') into Inventor objects."""
        inventors: list[Inventor] = []
        for name in inventor_names:
            if "," in name:
                parts = name.split(",", 1)
                last = parts[0].strip()
                first = parts[1].strip()
            else:
                last = name.strip()
                first = ""
            inventors.append(Inventor(first=first, last=last))
        return inventors

    @staticmethod
    def _parse_assignees(assignee_names: list[str]) -> list[Assignee]:
        """Parse assignee name strings into Assignee objects."""
        return [Assignee(organization=name.strip()) for name in assignee_names]

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

register_provider("uspto_odp", USPTOODPProvider)
