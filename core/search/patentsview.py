"""PatentsView search provider.

Implements the SearchProvider interface against the PatentsView REST API
(https://search.patentsview.org/api/v1/patent/).

Authentication:  X-Api-Key header.
Rate limit:      45 requests / minute.
Query language:  JSON operators (_text_any, _and, _gte, _lte, _contains, …).
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from core.models.patent import Assignee, Inventor, PatentType, SearchResult, SearchStrategy
from core.search.base import SearchProvider, SearchQuery, SearchResponse
from core.search.registry import register_provider

logger = structlog.get_logger(__name__)

_ENDPOINT = "https://search.patentsview.org/api/v1/patent/"

_FIELDS = [
    "patent_id",
    "patent_title",
    "patent_abstract",
    "patent_date",
    "patent_type",
    "patent_num_claims",
    "inventors.inventor_name_first",
    "inventors.inventor_name_last",
    "assignees.assignee_organization",
    "cpc_current.cpc_subsection_id",
]

_ERROR_MESSAGES: dict[int, str] = {
    400: "400 Bad query: malformed request body",
    403: "403 Invalid API key or access forbidden",
    429: "429 Rate limit exceeded: slow down requests",
    500: "500 PatentsView server error",
}


class PatentsViewProvider(SearchProvider):
    """Concrete SearchProvider for the PatentsView API."""

    provider_name: str = "patentsview"
    api_key: str = ""

    # -----------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------

    async def search(self, query: SearchQuery) -> SearchResponse:  # type: ignore[override]
        """Execute a patent search against PatentsView and return a SearchResponse."""
        start = time.monotonic()
        log = logger.bind(provider=self.provider_name, query=query.query, strategies=query.strategies)

        q_body = self._build_query(query)
        body: dict[str, Any] = {
            "q": q_body,
            "f": _FIELDS,
            "s": [{"patent_date": "desc"}],
            "o": {"per_page": query.max_results},
        }

        try:
            async with httpx.AsyncClient(
                headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
                timeout=30.0,
            ) as client:
                log.info("patentsview_api_call", endpoint=_ENDPOINT)
                resp = await client.post(_ENDPOINT, json=body)
        except httpx.RequestError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            log.error("patentsview_network_error", error=str(exc), duration_ms=duration_ms)
            return SearchResponse(
                results=[],
                provider=self.provider_name,
                duration_ms=duration_ms,
                error=f"Network error: {exc}",
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        log.info("patentsview_api_response", status=resp.status_code, duration_ms=duration_ms)

        if resp.status_code != 200:
            error_msg = _ERROR_MESSAGES.get(
                resp.status_code,
                f"{resp.status_code} Unexpected error from PatentsView",
            )
            log.error("patentsview_api_error", status=resp.status_code, message=error_msg)
            return SearchResponse(
                results=[],
                provider=self.provider_name,
                duration_ms=duration_ms,
                error=error_msg,
            )

        data = resp.json()
        results = self._parse_results(data, query)
        total_hits = data.get("total_hits", len(results))

        log.info("patentsview_search_complete", results=len(results), total_hits=total_hits)
        return SearchResponse(
            results=results,
            provider=self.provider_name,
            duration_ms=duration_ms,
            total_hits=total_hits,
        )

    async def health_check(self) -> bool:  # type: ignore[override]
        """Make a minimal query to verify connectivity and API key validity."""
        log = logger.bind(provider=self.provider_name)
        try:
            async with httpx.AsyncClient(
                headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
                timeout=10.0,
            ) as client:
                body = {
                    "q": {"_text_any": {"patent_title": "patent"}},
                    "f": ["patent_id"],
                    "o": {"per_page": 1},
                }
                resp = await client.post(_ENDPOINT, json=body)
                ok = resp.status_code == 200
                log.info("patentsview_health_check", status=resp.status_code, ok=ok)
                return ok
        except httpx.RequestError as exc:
            log.error("patentsview_health_check_failed", error=str(exc))
            return False

    # -----------------------------------------------------------------
    # Query building
    # -----------------------------------------------------------------

    def _build_query(self, query: SearchQuery) -> dict[str, Any]:
        """Translate a SearchQuery into a PatentsView query object."""
        clauses: list[dict[str, Any]] = []

        strategies = set(query.strategies)

        # --- Keyword ---
        if "keyword" in strategies and query.query:
            clauses.append(
                {
                    "_text_any": {
                        "patent_title": query.query,
                        "patent_abstract": query.query,
                    }
                }
            )

        # --- CPC classification ---
        if "classification" in strategies and query.cpc_codes:
            if len(query.cpc_codes) == 1:
                clauses.append(
                    {"_eq": {"cpc_current.cpc_subsection_id": query.cpc_codes[0]}}
                )
            else:
                clauses.append(
                    {
                        "_or": [
                            {"_eq": {"cpc_current.cpc_subsection_id": code}}
                            for code in query.cpc_codes
                        ]
                    }
                )

        # --- Inventor ---
        if "inventor" in strategies and query.inventors:
            if len(query.inventors) == 1:
                clauses.append(
                    {"_eq": {"inventors.inventor_name_last": query.inventors[0]}}
                )
            else:
                clauses.append(
                    {
                        "_or": [
                            {"_eq": {"inventors.inventor_name_last": name}}
                            for name in query.inventors
                        ]
                    }
                )

        # --- Assignee ---
        if "assignee" in strategies and query.assignees:
            if len(query.assignees) == 1:
                clauses.append(
                    {"_contains": {"assignees.assignee_organization": query.assignees[0]}}
                )
            else:
                clauses.append(
                    {
                        "_or": [
                            {"_contains": {"assignees.assignee_organization": org}}
                            for org in query.assignees
                        ]
                    }
                )

        # --- Date range ---
        if "date_range" in strategies and query.date_range:
            date_clauses: list[dict[str, Any]] = []
            start = query.date_range.get("start")
            end = query.date_range.get("end")
            if start:
                date_clauses.append({"_gte": {"patent_date": start}})
            if end:
                date_clauses.append({"_lte": {"patent_date": end}})
            if len(date_clauses) == 1:
                clauses.extend(date_clauses)
            elif len(date_clauses) > 1:
                clauses.append({"_and": date_clauses})

        # --- Combine ---
        if not clauses:
            # Fallback: broad keyword search if query text exists
            if query.query:
                return {"_text_any": {"patent_title": query.query, "patent_abstract": query.query}}
            # Last resort: return everything (not ideal but avoids empty query error)
            return {"_gte": {"patent_date": "1900-01-01"}}

        if len(clauses) == 1:
            return clauses[0]

        return {"_and": clauses}

    # -----------------------------------------------------------------
    # Response parsing
    # -----------------------------------------------------------------

    def _parse_results(self, data: dict[str, Any], query: SearchQuery) -> list[SearchResult]:
        """Parse PatentsView response JSON into SearchResult objects."""
        raw_patents: list[dict[str, Any]] = data.get("patents") or []
        strategy = self._primary_strategy(query)
        results: list[SearchResult] = []

        for raw in raw_patents:
            inventors = [
                Inventor(
                    first=inv.get("inventor_name_first", ""),
                    last=inv.get("inventor_name_last", ""),
                )
                for inv in (raw.get("inventors") or [])
            ]

            assignees = [
                Assignee(organization=asgn.get("assignee_organization"))
                for asgn in (raw.get("assignees") or [])
            ]

            cpc_codes = [
                cpc["cpc_subsection_id"]
                for cpc in (raw.get("cpc_current") or [])
                if "cpc_subsection_id" in cpc
            ]

            patent_type_raw = raw.get("patent_type")
            try:
                patent_type = PatentType(patent_type_raw) if patent_type_raw else None
            except ValueError:
                patent_type = None

            results.append(
                SearchResult(
                    patent_id=raw["patent_id"],
                    title=raw.get("patent_title", ""),
                    abstract=raw.get("patent_abstract") or None,
                    patent_date=raw.get("patent_date") or None,
                    patent_type=patent_type,
                    inventors=inventors,
                    assignees=assignees,
                    cpc_codes=cpc_codes,
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

register_provider("patentsview", PatentsViewProvider)
