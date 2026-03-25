"""Tests for core/analysis/prior_art.py — TDD: written before implementation."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.llm.base import LLMProvider, LLMResponse
from core.models.patent import SearchResult, SearchStrategy, PatentType
from core.analysis.base import (
    AnalysisSeverity,
    AnalysisStatus,
    AnalysisFinding,
    AnalysisResult,
)
from core.analysis.prior_art import PriorArtAnalyzer


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_llm(response_text: str = "OVERLAP: None.\nDISTINGUISHING: Invention is novel.\nSEVERITY: low\nSUGGESTION: No changes needed.\nSTATUS: clear") -> LLMProvider:
    """Return a mock LLMProvider whose generate() returns a canned response."""
    provider = MagicMock(spec=LLMProvider)
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content=response_text,
            model="mock-model",
            tokens_used=100,
        )
    )
    return provider


def _make_search_result(patent_id: str = "US1234567", title: str = "Example Patent") -> SearchResult:
    return SearchResult(
        patent_id=patent_id,
        title=title,
        abstract="A widget for doing things.",
        provider="mock",
        strategy=SearchStrategy.KEYWORD,
    )


CLEAR_RESPONSE = (
    "OVERLAP: None.\n"
    "DISTINGUISHING: Invention is wholly novel.\n"
    "SEVERITY: low\n"
    "SUGGESTION: No changes needed.\n"
    "STATUS: clear"
)

CAUTION_RESPONSE = (
    "OVERLAP: Partial overlap in claim 1 methodology.\n"
    "DISTINGUISHING: Different substrate material used.\n"
    "SEVERITY: medium\n"
    "SUGGESTION: Narrow claim 1 to exclude shared methodology.\n"
    "STATUS: caution"
)

CONFLICT_RESPONSE = (
    "OVERLAP: Direct anticipation — all claim elements present.\n"
    "DISTINGUISHING: None identified.\n"
    "SEVERITY: high\n"
    "SUGGESTION: Abandon or substantially amend claims.\n"
    "STATUS: conflict"
)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_prior_art_analyzer_has_module_name():
    llm = _make_llm()
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    assert analyzer.module_name == "prior_art"


def test_prior_art_analyzer_stores_provider():
    llm = _make_llm()
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    assert analyzer.llm_provider is llm


# ---------------------------------------------------------------------------
# No results → CLEAR
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_search_results_returns_clear():
    llm = _make_llm()
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    result = await analyzer.analyze("A novel widget", search_results=[])

    assert isinstance(result, AnalysisResult)
    assert result.module == "prior_art"
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    # LLM should NOT have been called — no prior art to compare against
    llm.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Single prior art result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_result_clear_produces_finding():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    result = await analyzer.analyze("A novel widget", search_results=[_make_search_result()])

    assert result.status == AnalysisStatus.CLEAR
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert isinstance(finding, AnalysisFinding)
    assert finding.severity == AnalysisSeverity.LOW
    assert finding.prior_art_id == "US1234567"


@pytest.mark.asyncio
async def test_single_result_caution_produces_finding():
    llm = _make_llm(CAUTION_RESPONSE)
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    result = await analyzer.analyze("A novel widget", search_results=[_make_search_result()])

    assert result.status == AnalysisStatus.CAUTION
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.severity == AnalysisSeverity.MEDIUM
    assert "Narrow" in finding.suggestion


@pytest.mark.asyncio
async def test_single_result_conflict_produces_finding():
    llm = _make_llm(CONFLICT_RESPONSE)
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    result = await analyzer.analyze("A novel widget", search_results=[_make_search_result()])

    assert result.status == AnalysisStatus.CONFLICT
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.severity == AnalysisSeverity.HIGH


# ---------------------------------------------------------------------------
# Multiple results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_results_produce_finding_per_result():
    """Two results → two LLM calls → two findings."""
    results = [
        _make_search_result("US1111111", "First Patent"),
        _make_search_result("US2222222", "Second Patent"),
    ]
    llm = _make_llm(CAUTION_RESPONSE)
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    result = await analyzer.analyze("A novel widget", search_results=results)

    assert len(result.findings) == 2
    assert llm.generate.call_count == 2
    patent_ids = {f.prior_art_id for f in result.findings}
    assert patent_ids == {"US1111111", "US2222222"}


@pytest.mark.asyncio
async def test_multiple_mixed_status_uses_worst_case():
    """CLEAR + CONFLICT → overall CONFLICT."""
    results = [
        _make_search_result("US1111111", "First Patent"),
        _make_search_result("US2222222", "Second Patent"),
    ]
    # First call returns clear, second returns conflict
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(
        side_effect=[
            LLMResponse(content=CLEAR_RESPONSE, model="mock", tokens_used=10),
            LLMResponse(content=CONFLICT_RESPONSE, model="mock", tokens_used=10),
        ]
    )
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    result = await analyzer.analyze("A novel widget", search_results=results)

    assert result.status == AnalysisStatus.CONFLICT


@pytest.mark.asyncio
async def test_multiple_clear_results_overall_clear():
    """All CLEAR → overall CLEAR."""
    results = [
        _make_search_result("US1111111", "First Patent"),
        _make_search_result("US2222222", "Second Patent"),
    ]
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    result = await analyzer.analyze("A novel widget", search_results=results)

    assert result.status == AnalysisStatus.CLEAR
    assert len(result.findings) == 2


# ---------------------------------------------------------------------------
# LLM error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_error_handled_gracefully():
    """LLM raises an exception → returns error finding, does not propagate."""
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=RuntimeError("Connection refused"))
    analyzer = PriorArtAnalyzer(llm_provider=llm)

    result = await analyzer.analyze(
        "A novel widget", search_results=[_make_search_result()]
    )

    assert isinstance(result, AnalysisResult)
    assert result.module == "prior_art"
    # Should surface the error as a HIGH-severity finding rather than crashing
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.severity == AnalysisSeverity.HIGH
    assert "error" in finding.description.lower() or "failed" in finding.description.lower()


@pytest.mark.asyncio
async def test_llm_error_does_not_crash_multiple_results():
    """Only the failing result gets an error finding; others are processed."""
    results = [
        _make_search_result("US1111111", "Good Patent"),
        _make_search_result("US2222222", "Bad Patent"),
    ]
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(
        side_effect=[
            LLMResponse(content=CLEAR_RESPONSE, model="mock", tokens_used=10),
            RuntimeError("Timeout"),
        ]
    )
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    result = await analyzer.analyze("A novel widget", search_results=results)

    assert len(result.findings) == 2
    severities = {f.severity for f in result.findings}
    assert AnalysisSeverity.HIGH in severities  # error finding


# ---------------------------------------------------------------------------
# Status determination logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_caution_without_conflict_yields_caution():
    """CLEAR + CAUTION → overall CAUTION (not CLEAR, not CONFLICT)."""
    results = [
        _make_search_result("US1111111", "Clear Patent"),
        _make_search_result("US2222222", "Caution Patent"),
    ]
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(
        side_effect=[
            LLMResponse(content=CLEAR_RESPONSE, model="mock", tokens_used=10),
            LLMResponse(content=CAUTION_RESPONSE, model="mock", tokens_used=10),
        ]
    )
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    result = await analyzer.analyze("A novel widget", search_results=results)

    assert result.status == AnalysisStatus.CAUTION


# ---------------------------------------------------------------------------
# LLM prompt includes invention and prior art
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_prompt_contains_invention_description():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    invention = "A self-cleaning toothbrush with nano-bristles"
    await analyzer.analyze(invention, search_results=[_make_search_result()])

    call_args = llm.generate.call_args
    prompt_or_kwargs = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert invention in prompt_or_kwargs


@pytest.mark.asyncio
async def test_llm_system_prompt_is_set():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    await analyzer.analyze("A widget", search_results=[_make_search_result()])

    call_kwargs = llm.generate.call_args[1] if llm.generate.call_args[1] else {}
    if not call_kwargs:
        call_kwargs = {}
        # system may be positional arg[1]
        args = llm.generate.call_args[0]
        if len(args) > 1:
            system_arg = args[1]
        else:
            system_arg = llm.generate.call_args.kwargs.get("system", "")
    else:
        system_arg = call_kwargs.get("system", "")

    assert system_arg, "System prompt must be provided"
    assert "patent" in system_arg.lower()


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_result_has_recommendation():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    result = await analyzer.analyze("A widget", search_results=[_make_search_result()])

    assert result.recommendation
    assert isinstance(result.recommendation, str)


@pytest.mark.asyncio
async def test_finding_has_statute():
    llm = _make_llm(CONFLICT_RESPONSE)
    analyzer = PriorArtAnalyzer(llm_provider=llm)
    result = await analyzer.analyze("A widget", search_results=[_make_search_result()])

    finding = result.findings[0]
    assert finding.statute
    assert "35 USC" in finding.statute or "USC" in finding.statute
