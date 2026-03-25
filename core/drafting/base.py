"""Abstract base interface for patent application drafters.

All concrete drafters must subclass Drafter and implement the draft() method.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import structlog

from core.llm.base import LLMProvider
from core.models.application import DraftApplication
from core.models.patent import SearchResult

logger = structlog.get_logger(__name__)


class Drafter(ABC):
    """Abstract base class for all patent application drafters.

    Subclasses receive an LLMProvider at construction time and must implement
    the draft() method to produce a DraftApplication from an invention description.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    @abstractmethod
    async def draft(
        self,
        invention_description: str,
        prior_art_results: list[SearchResult] | None = None,
        preferences: dict | None = None,
    ) -> DraftApplication:
        """Generate a DraftApplication from an invention description.

        Args:
            invention_description: Free-text description of the invention.
            prior_art_results: Optional list of prior art search results to
                               inform claim differentiation and specification.
            preferences: Optional dict of user/workflow preferences (e.g.
                         claim_breadth, num_embodiments).

        Returns:
            A DraftApplication populated with the drafter's output.
        """

    def _build_prior_art_context(self, results: list[SearchResult] | None) -> str:
        """Summarize prior art search results for inclusion in an LLM prompt.

        Args:
            results: A list of SearchResult objects or None.

        Returns:
            A formatted string summarising the prior art, or an empty string
            if no results are provided.
        """
        if not results:
            return ""

        log = logger.bind(num_prior_art=len(results))
        log.debug("drafter.prior_art_context.building")

        lines: list[str] = ["PRIOR ART REFERENCES:"]
        for i, sr in enumerate(results, start=1):
            lines.append(f"\n[{i}] Patent ID: {sr.patent_id}")
            lines.append(f"    Title: {sr.title}")
            if sr.abstract:
                lines.append(f"    Abstract: {sr.abstract}")
            if sr.relevance_score is not None:
                lines.append(f"    Relevance score: {sr.relevance_score:.2f}")
            if sr.relevance_notes:
                lines.append(f"    Notes: {sr.relevance_notes}")

        context = "\n".join(lines)
        log.debug("drafter.prior_art_context.built", length=len(context))
        return context
