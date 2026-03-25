"""Tests for core/analysis/novelty.py — 35 USC 102 Novelty analysis."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.llm.base import LLMProvider, LLMResponse
from core.models.patent import Claim, SearchResult, SearchStrategy
from core.analysis.base import (
    AnalysisSeverity,
    AnalysisStatus,
    AnalysisFinding,
    AnalysisResult,
)
from core.analysis.novelty import NoveltyAnalyzer


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_llm(response_text: str = "") -> LLMProvider:
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
        abstract="A method and system for doing something.",
        provider="mock",
        strategy=SearchStrategy.KEYWORD,
    )


def _make_claim(number: int = 1, text: str = "A method comprising: step A; step B.") -> Claim:
    return Claim(number=number, type="independent", text=text)


CLEAR_RESPONSE = (
    "ANTICIPATED: No\n"
    "MISSING_ELEMENTS: step B is not disclosed\n"
    "SEVERITY: low\n"
    "SUGGESTION: Claim 1 appears novel over this reference.\n"
    "STATUS: clear"
)

CAUTION_RESPONSE = (
    "ANTICIPATED: Partially\n"
    "MISSING_ELEMENTS: step A partially overlaps\n"
    "SEVERITY: medium\n"
    "SUGGESTION: Narrow claim 1 to specify a unique variant of step A.\n"
    "STATUS: caution"
)

CONFLICT_RESPONSE = (
    "ANTICIPATED: Yes\n"
    "MISSING_ELEMENTS: None — all elements present in reference\n"
    "SEVERITY: high\n"
    "SUGGESTION: Claim 1 is anticipated; amend or abandon.\n"
    "STATUS: conflict"
)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_novelty_analyzer_module_name():
    analyzer = NoveltyAnalyzer(llm_provider=_make_llm())
    assert analyzer.module_name == "novelty"


def test_novelty_analyzer_stores_provider():
    llm = _make_llm()
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    assert analyzer.llm_provider is llm


# ---------------------------------------------------------------------------
# Empty inputs → CLEAR
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_search_results_returns_clear():
    llm = _make_llm()
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[],
        claims=[_make_claim()],
    )
    assert isinstance(result, AnalysisResult)
    assert result.module == "novelty"
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_no_claims_returns_clear():
    llm = _make_llm()
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[],
    )
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_none_claims_returns_clear():
    llm = _make_llm()
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=None,
    )
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []


# ---------------------------------------------------------------------------
# Single result — status levels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_clear_result():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CLEAR
    assert len(result.findings) == 1
    assert result.findings[0].severity == AnalysisSeverity.LOW


@pytest.mark.asyncio
async def test_single_caution_result():
    llm = _make_llm(CAUTION_RESPONSE)
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CAUTION
    assert result.findings[0].severity == AnalysisSeverity.MEDIUM


@pytest.mark.asyncio
async def test_single_conflict_result():
    llm = _make_llm(CONFLICT_RESPONSE)
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CONFLICT
    assert result.findings[0].severity == AnalysisSeverity.HIGH


# ---------------------------------------------------------------------------
# Multiple results — worst-case aggregation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mixed_results_worst_case_conflict():
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(
        side_effect=[
            LLMResponse(content=CLEAR_RESPONSE, model="mock", tokens_used=10),
            LLMResponse(content=CONFLICT_RESPONSE, model="mock", tokens_used=10),
        ]
    )
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result("US1"), _make_search_result("US2")],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CONFLICT
    assert len(result.findings) == 2


@pytest.mark.asyncio
async def test_all_clear_results_stay_clear():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result("US1"), _make_search_result("US2")],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CLEAR
    assert len(result.findings) == 2


# ---------------------------------------------------------------------------
# LLM error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_error_handled_gracefully():
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=RuntimeError("Connection refused"))
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim()],
    )
    assert isinstance(result, AnalysisResult)
    assert len(result.findings) == 1
    assert result.findings[0].severity == AnalysisSeverity.HIGH
    assert "error" in result.findings[0].description.lower() or "failed" in result.findings[0].description.lower()


# ---------------------------------------------------------------------------
# Statute and result structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finding_statute_is_102():
    llm = _make_llm(CONFLICT_RESPONSE)
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim()],
    )
    assert "35 USC 102" in result.findings[0].statute or "102" in result.findings[0].statute


@pytest.mark.asyncio
async def test_result_has_recommendation():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim()],
    )
    assert result.recommendation
    assert isinstance(result.recommendation, str)


@pytest.mark.asyncio
async def test_llm_prompt_includes_claim_text():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    claim_text = "A unique apparatus comprising element Z"
    await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim(text=claim_text)],
    )
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert claim_text in prompt


@pytest.mark.asyncio
async def test_finding_prior_art_id_is_set():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = NoveltyAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result(patent_id="US9999999")],
        claims=[_make_claim()],
    )
    assert result.findings[0].prior_art_id == "US9999999"
