"""Tests for core/analysis/obviousness.py — 35 USC 103 Obviousness analysis."""
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
from core.analysis.obviousness import ObviousnessAnalyzer


# ---------------------------------------------------------------------------
# Helpers
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
        abstract="A system for processing data.",
        provider="mock",
        strategy=SearchStrategy.KEYWORD,
    )


def _make_claim(number: int = 1, text: str = "A method comprising: step A; step B.") -> Claim:
    return Claim(number=number, type="independent", text=text)


CLEAR_RESPONSE = (
    "OBVIOUS: No\n"
    "DIFFERENCES: The combination lacks motivation to combine\n"
    "SECONDARY_CONSIDERATIONS: Commercial success noted\n"
    "SEVERITY: low\n"
    "SUGGESTION: The claims appear non-obvious over this combination.\n"
    "STATUS: clear"
)

CAUTION_RESPONSE = (
    "OBVIOUS: Possibly\n"
    "DIFFERENCES: Minor variation that skilled person might attempt\n"
    "SECONDARY_CONSIDERATIONS: None identified\n"
    "SEVERITY: medium\n"
    "SUGGESTION: Consider adding a claim limitation to differentiate.\n"
    "STATUS: caution"
)

CONFLICT_RESPONSE = (
    "OBVIOUS: Yes\n"
    "DIFFERENCES: Trivial substitution of known elements\n"
    "SECONDARY_CONSIDERATIONS: None\n"
    "SEVERITY: high\n"
    "SUGGESTION: Claims are likely obvious; substantial amendment required.\n"
    "STATUS: conflict"
)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_obviousness_analyzer_module_name():
    analyzer = ObviousnessAnalyzer(llm_provider=_make_llm())
    assert analyzer.module_name == "obviousness"


def test_obviousness_analyzer_stores_provider():
    llm = _make_llm()
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
    assert analyzer.llm_provider is llm


# ---------------------------------------------------------------------------
# Empty inputs → CLEAR
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_search_results_returns_clear():
    llm = _make_llm()
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_no_claims_returns_clear():
    llm = _make_llm()
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
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
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=None,
    )
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []


# ---------------------------------------------------------------------------
# Single reference analysis
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_clear_result():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
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
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
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
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CONFLICT
    assert result.findings[0].severity == AnalysisSeverity.HIGH


# ---------------------------------------------------------------------------
# Multiple references — worst-case aggregation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_results_worst_case():
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(
        side_effect=[
            LLMResponse(content=CLEAR_RESPONSE, model="mock", tokens_used=10),
            LLMResponse(content=CONFLICT_RESPONSE, model="mock", tokens_used=10),
        ]
    )
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result("US1"), _make_search_result("US2")],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CONFLICT
    assert len(result.findings) == 2


@pytest.mark.asyncio
async def test_caution_without_conflict_stays_caution():
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(
        side_effect=[
            LLMResponse(content=CLEAR_RESPONSE, model="mock", tokens_used=10),
            LLMResponse(content=CAUTION_RESPONSE, model="mock", tokens_used=10),
        ]
    )
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result("US1"), _make_search_result("US2")],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CAUTION


# ---------------------------------------------------------------------------
# LLM error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_error_handled_gracefully():
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=RuntimeError("Timeout"))
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim()],
    )
    assert isinstance(result, AnalysisResult)
    assert len(result.findings) == 1
    assert result.findings[0].severity == AnalysisSeverity.HIGH
    description_lower = result.findings[0].description.lower()
    assert "error" in description_lower or "failed" in description_lower


# ---------------------------------------------------------------------------
# Graham factors and structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_system_prompt_mentions_graham_or_103():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
    await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim()],
    )
    call_kwargs = llm.generate.call_args.kwargs if llm.generate.call_args.kwargs else {}
    system_arg = call_kwargs.get("system", "")
    if not system_arg:
        args = llm.generate.call_args[0]
        system_arg = args[1] if len(args) > 1 else ""
    assert system_arg
    lower = system_arg.lower()
    assert "103" in lower or "obvious" in lower or "graham" in lower


@pytest.mark.asyncio
async def test_finding_statute_is_103():
    llm = _make_llm(CONFLICT_RESPONSE)
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim()],
    )
    assert "103" in result.findings[0].statute


@pytest.mark.asyncio
async def test_result_has_recommendation():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim()],
    )
    assert result.recommendation
    assert isinstance(result.recommendation, str)


@pytest.mark.asyncio
async def test_prompt_includes_claim_text():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = ObviousnessAnalyzer(llm_provider=llm)
    claim_text = "A unique process comprising novel element Q"
    await analyzer.analyze(
        "A method for X",
        search_results=[_make_search_result()],
        claims=[_make_claim(text=claim_text)],
    )
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert claim_text in prompt
