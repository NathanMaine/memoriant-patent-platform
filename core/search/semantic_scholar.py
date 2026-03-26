"""Semantic Scholar non-patent literature (NPL) search provider.

Implements the SearchProvider interface against the Semantic Scholar Graph API:
  GET https://api.semanticscholar.org/graph/v1/paper/search?query=...

This is a FREE, opt-in provider (no API key required for basic use).
Results are marked as non-patent literature with the 'NPL-' prefix on patent_id.

Authentication:  None required for basic rate-limited access.
Rate limits:     100 requests per 5 minutes (unauthenticated).
Documentation:   https://api.semanticscholar.org/api-docs/
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from core.models.patent import SearchResult, SearchStrategy
from core.search.base import SearchProvider, SearchQuery, SearchResponse
from core.search.registry import register_provider

logger = structlog.get_logger(__name__)

_ENDPOINT = "https://api.semanticscholar.org/graph/v1/paper/search"

_FIELDS = "paperId,title,abstract,tldr"

_ERROR_MESSAGES: dict[int, str] = {
    429: "429 Rate limit exceeded: slow down requests to Semantic Scholar",
    500: "500 Semantic Scholar server error",
    503: "503 Semantic Scholar service unavailable",
}


class SemanticScholarProvider(SearchProvider):
    """Concrete SearchProvider for the Semantic Scholar Graph API.

    Returns non-patent literature results with patent_id prefixed 'NPL-'.
    This provider is FREE and opt-in.  Pass ``semantic_scholar_enabled=True``
    to ``SearchRegistry.get_enabled()`` to activate it.
    """

    provider_name: str = "semantic_scholar"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search(self, query: SearchQuery) -> SearchResponse:
        """Execute a Semantic Scholar paper search and return a SearchResponse."""
        start_time = time.monotonic()
        log = logger.bind(provider=self.provider_name, query=query.query)

        params: dict[str, Any] = {
            "query": query.query,
            "limit": min(query.max_results, 100),  # API max is 100
            "fields": _FIELDS,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                log.info("semantic_scholar_api_call", endpoint=_ENDPOINT, query=query.query)
                resp = client.get(_ENDPOINT, params=params)
        except httpx.TimeoutException as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log.error("semantic_scholar_timeout", error=str(exc), duration_ms=duration_ms)
            return SearchResponse(
                results=[],
                provider=self.provider_name,
                duration_ms=duration_ms,
                error=f"Timeout error: {exc}",
            )
        except httpx.RequestError as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log.error("semantic_scholar_network_error", error=str(exc), duration_ms=duration_ms)
            return SearchResponse(
                results=[],
                provider=self.provider_name,
                duration_ms=duration_ms,
                error=f"Network error: {exc}",
            )

        duration_ms = int((time.monotonic() - start_time) * 1000)
        log.info("semantic_scholar_api_response", status=resp.status_code, duration_ms=duration_ms)

        if resp.status_code != 200:
            error_msg = _ERROR_MESSAGES.get(
                resp.status_code,
                f"{resp.status_code} Unexpected error from Semantic Scholar",
            )
            log.error("semantic_scholar_api_error", status=resp.status_code, message=error_msg)
            return SearchResponse(
                results=[],
                provider=self.provider_name,
                duration_ms=duration_ms,
                error=error_msg,
            )

        data = resp.json()
        results = self._parse_results(data)
        total_hits = data.get("total", len(results))

        log.info("semantic_scholar_search_complete", results=len(results), total_hits=total_hits)
        return SearchResponse(
            results=results,
            provider=self.provider_name,
            duration_ms=duration_ms,
            total_hits=total_hits,
        )

    def health_check(self) -> bool:
        """Make a minimal query to verify Semantic Scholar is reachable."""
        log = logger.bind(provider=self.provider_name)
        params: dict[str, Any] = {
            "query": "patent",
            "limit": 1,
            "fields": "paperId,title",
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(_ENDPOINT, params=params)
                ok = resp.status_code == 200
                log.info("semantic_scholar_health_check", status=resp.status_code, ok=ok)
                return ok
        except httpx.RequestError as exc:
            log.error("semantic_scholar_health_check_failed", error=str(exc))
            return False

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_results(self, data: dict[str, Any]) -> list[SearchResult]:
        """Parse Semantic Scholar response JSON into SearchResult objects."""
        papers: list[dict[str, Any]] = data.get("data") or []
        results: list[SearchResult] = []

        for paper in papers:
            paper_id = paper.get("paperId", "")
            npl_id = f"NPL-{paper_id}"
            title = paper.get("title", "")

            # Prefer tldr (concise summary) over full abstract
            tldr = paper.get("tldr")
            if tldr and isinstance(tldr, dict):
                abstract = tldr.get("text") or paper.get("abstract") or None
            else:
                abstract = paper.get("abstract") or None

            results.append(
                SearchResult(
                    patent_id=npl_id,
                    title=title,
                    abstract=abstract,
                    provider=self.provider_name,
                    strategy=SearchStrategy.NPL,
                )
            )

        return results


# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------

register_provider("semantic_scholar", SemanticScholarProvider)
