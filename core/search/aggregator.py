"""Search aggregator — runs multiple providers in parallel and merges results.

Providers are executed concurrently via asyncio.gather(return_exceptions=True).
A single provider failure never kills the overall search; its error is captured
and surfaced in AggregatedSearchResponse.errors while the other providers
continue to contribute results.

Deduplication strategy: when the same patent_id appears from multiple providers
the result with the highest relevance_score is kept. If scores are equal the
first one encountered (by iteration order) is retained.

Sort order: relevance_score descending (None scores sort last), then
patent_date descending (None dates sort last within the same score bucket).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from pydantic import BaseModel

from core.models.patent import SearchResult
from core.search.base import SearchProvider, SearchQuery, SearchResponse

logger = structlog.get_logger(__name__)


class AggregatedSearchResponse(BaseModel):
    """Combined response from all search providers."""

    results: list[SearchResult]
    total_hits: int
    provider_responses: list[SearchResponse]
    duration_ms: int
    errors: list[str]


class SearchAggregator:
    """Runs multiple SearchProviders in parallel and merges their results."""

    def __init__(self, providers: list[SearchProvider]) -> None:
        self._providers = providers

    async def search(self, query: SearchQuery) -> AggregatedSearchResponse:
        """Execute all providers in parallel and return a merged, deduplicated response."""
        log = logger.bind(query=query.query, provider_count=len(self._providers))
        log.info("aggregator_search_start")

        start = time.monotonic()

        if not self._providers:
            duration_ms = int((time.monotonic() - start) * 1000)
            log.info("aggregator_search_complete", results=0, duration_ms=duration_ms)
            return AggregatedSearchResponse(
                results=[],
                total_hits=0,
                provider_responses=[],
                duration_ms=duration_ms,
                errors=[],
            )

        # Run all providers concurrently; capture exceptions rather than propagating
        raw_outcomes: list[SearchResponse | BaseException] = await asyncio.gather(
            *[self._run_provider(p, query) for p in self._providers],
            return_exceptions=True,
        )

        provider_responses: list[SearchResponse] = []
        errors: list[str] = []
        all_results: list[SearchResult] = []

        for provider, outcome in zip(self._providers, raw_outcomes):
            if isinstance(outcome, BaseException):
                msg = f"{provider.provider_name}: {outcome}"
                log.error(
                    "aggregator_provider_exception",
                    provider=provider.provider_name,
                    error=str(outcome),
                )
                errors.append(msg)
            else:
                # outcome is a SearchResponse
                if outcome.error:
                    errors.append(f"{outcome.provider}: {outcome.error}")
                provider_responses.append(outcome)
                all_results.extend(outcome.results)

        # Deduplicate: keep the result with the highest relevance_score per patent_id
        deduped = self._deduplicate(all_results)
        log.info(
            "aggregator_dedup_stats",
            before=len(all_results),
            after=len(deduped),
            duplicates_removed=len(all_results) - len(deduped),
        )

        # Sort: relevance_score desc (None → last), then patent_date desc (None → last)
        sorted_results = sorted(
            deduped,
            key=lambda r: (
                -(r.relevance_score if r.relevance_score is not None else float("-inf")),
                -(r.patent_date.toordinal() if r.patent_date is not None else 0),
            ),
        )

        duration_ms = int((time.monotonic() - start) * 1000)
        log.info(
            "aggregator_search_complete",
            results=len(sorted_results),
            total_hits=len(sorted_results),
            providers=len(provider_responses),
            errors=len(errors),
            duration_ms=duration_ms,
        )

        return AggregatedSearchResponse(
            results=sorted_results,
            total_hits=len(sorted_results),
            provider_responses=provider_responses,
            duration_ms=duration_ms,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_provider(
        self, provider: SearchProvider, query: SearchQuery
    ) -> SearchResponse:
        """Run a single provider and log its duration."""
        t0 = time.monotonic()
        result = await provider.search(query)
        elapsed = int((time.monotonic() - t0) * 1000)
        logger.info(
            "aggregator_provider_done",
            provider=provider.provider_name,
            results=len(result.results),
            duration_ms=elapsed,
        )
        return result

    @staticmethod
    def _deduplicate(results: list[SearchResult]) -> list[SearchResult]:
        """Return one SearchResult per patent_id, keeping the highest relevance_score."""
        best: dict[str, SearchResult] = {}
        for result in results:
            pid = result.patent_id
            if pid not in best:
                best[pid] = result
            else:
                existing_score = best[pid].relevance_score
                new_score = result.relevance_score
                # Prefer the result with a defined, higher score
                if new_score is not None and (
                    existing_score is None or new_score > existing_score
                ):
                    best[pid] = result
        return list(best.values())
