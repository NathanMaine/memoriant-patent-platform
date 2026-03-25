"""Abstract base interface for patent search providers.

All concrete search providers must subclass SearchProvider and implement
the search() and health_check() methods.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import structlog
from pydantic import BaseModel, Field

from core.models.patent import SearchResult

logger = structlog.get_logger(__name__)


class SearchQuery(BaseModel):
    """Parameters for a patent search request."""

    query: str
    strategies: list[str] = Field(default_factory=lambda: ["keyword"])
    date_range: dict | None = None
    cpc_codes: list[str] = Field(default_factory=list)
    inventors: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    max_results: int = 50


class SearchResponse(BaseModel):
    """Response envelope returned by every search provider."""

    results: list[SearchResult]
    provider: str
    duration_ms: int
    total_hits: int = 0
    error: str | None = None


class SearchProvider(ABC, BaseModel):
    """Abstract base class all concrete search providers must implement.

    Subclasses must declare a ``provider_name`` class attribute and implement
    both ``search()`` and ``health_check()``.
    """

    provider_name: str

    model_config = {"arbitrary_types_allowed": True}

    @abstractmethod
    def search(self, query: SearchQuery) -> SearchResponse:
        """Execute a patent search and return a SearchResponse."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the provider is reachable and operational."""
