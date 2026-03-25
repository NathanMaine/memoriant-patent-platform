"""Shared types for all analysis modules.

Every analysis module returns an AnalysisResult built from AnalysisFinding
instances and is implemented as a concrete AnalysisModule subclass.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel

from core.models.patent import Claim, SearchResult


class AnalysisSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnalysisStatus(StrEnum):
    CLEAR = "clear"
    CAUTION = "caution"
    CONFLICT = "conflict"


class AnalysisFinding(BaseModel):
    """A single finding produced by an analysis module."""

    prior_art_id: str | None = None
    description: str
    severity: AnalysisSeverity
    suggestion: str
    statute: str  # e.g., "35 USC 102", "MPEP 608"


class AnalysisResult(BaseModel):
    """The aggregated output of one analysis module run."""

    module: str  # e.g., "novelty", "obviousness", "claims"
    status: AnalysisStatus
    findings: list[AnalysisFinding]
    recommendation: str


class AnalysisModule(ABC):
    """Abstract base class all concrete analysis modules must implement."""

    module_name: str

    @abstractmethod
    async def analyze(
        self,
        invention_description: str,
        search_results: list[SearchResult],
        claims: list[Claim] | None = None,
        specification: str | None = None,
    ) -> AnalysisResult: ...
