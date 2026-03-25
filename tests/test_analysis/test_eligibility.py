"""Tests for core/analysis/eligibility.py — 35 USC 101 Eligibility (Alice/Mayo)."""
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
from core.analysis.eligibility import EligibilityAnalyzer


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


def _make_claim(
    number: int = 1,
    text: str = "A method comprising: receiving data; transforming data; outputting result.",
) -> Claim:
    return Claim(number=number, type="independent", text=text)


CLEAR_RESPONSE = (
    "ABSTRACT_IDEA: No\n"
    "STEP_ONE: Claim is directed to a specific technical improvement\n"
    "STEP_TWO: N/A — not directed to abstract idea\n"
    "SIGNIFICANTLY_MORE: N/A\n"
    "SEVERITY: low\n"
    "SUGGESTION: Claim appears patent-eligible as drafted.\n"
    "STATUS: clear"
)

CAUTION_RESPONSE = (
    "ABSTRACT_IDEA: Possibly\n"
    "STEP_ONE: Claim may be directed to an abstract idea of data processing\n"
    "STEP_TWO: Possibly includes significantly more through hardware integration\n"
    "SIGNIFICANTLY_MORE: Unclear — additional claim limitations may be needed\n"
    "SEVERITY: medium\n"
    "SUGGESTION: Add specific technical implementation details to distinguish from abstract idea.\n"
    "STATUS: caution"
)

CONFLICT_RESPONSE = (
    "ABSTRACT_IDEA: Yes\n"
    "STEP_ONE: Claim is directed to the abstract idea of mathematical processing\n"
    "STEP_TWO: No significantly more — routine computer implementation only\n"
    "SIGNIFICANTLY_MORE: Not present\n"
    "SEVERITY: high\n"
    "SUGGESTION: Claims are likely ineligible under Alice; substantial redrafting required.\n"
    "STATUS: conflict"
)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_eligibility_analyzer_module_name():
    analyzer = EligibilityAnalyzer(llm_provider=_make_llm())
    assert analyzer.module_name == "eligibility"


def test_eligibility_analyzer_stores_provider():
    llm = _make_llm()
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    assert analyzer.llm_provider is llm


# ---------------------------------------------------------------------------
# Empty inputs → CLEAR
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_claims_returns_clear():
    llm = _make_llm()
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[],
    )
    assert isinstance(result, AnalysisResult)
    assert result.module == "eligibility"
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_none_claims_returns_clear():
    llm = _make_llm()
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=None,
    )
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    llm.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Eligibility does not require search results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_eligibility_works_without_search_results():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A physical device",
        search_results=[],
        claims=[_make_claim()],
    )
    assert isinstance(result, AnalysisResult)


# ---------------------------------------------------------------------------
# Status levels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clear_response():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A physical device",
        search_results=[],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CLEAR
    assert len(result.findings) == 1
    assert result.findings[0].severity == AnalysisSeverity.LOW


@pytest.mark.asyncio
async def test_caution_response():
    llm = _make_llm(CAUTION_RESPONSE)
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A software method",
        search_results=[],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CAUTION
    assert result.findings[0].severity == AnalysisSeverity.MEDIUM


@pytest.mark.asyncio
async def test_conflict_response():
    llm = _make_llm(CONFLICT_RESPONSE)
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A pure math method",
        search_results=[],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CONFLICT
    assert result.findings[0].severity == AnalysisSeverity.HIGH


# ---------------------------------------------------------------------------
# Multiple claims — worst-case aggregation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_claims_produce_findings():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A physical device",
        search_results=[],
        claims=[_make_claim(1), _make_claim(2, "An apparatus comprising a processor.")],
    )
    assert len(result.findings) == 2


@pytest.mark.asyncio
async def test_multiple_claims_worst_case_conflict():
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(
        side_effect=[
            LLMResponse(content=CLEAR_RESPONSE, model="mock", tokens_used=10),
            LLMResponse(content=CONFLICT_RESPONSE, model="mock", tokens_used=10),
        ]
    )
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A mixed device",
        search_results=[],
        claims=[_make_claim(1), _make_claim(2, "A method of pure mathematical steps.")],
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
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A software method",
        search_results=[],
        claims=[_make_claim(1), _make_claim(2, "A method of processing data.")],
    )
    assert result.status == AnalysisStatus.CAUTION


# ---------------------------------------------------------------------------
# LLM error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_error_handled_gracefully():
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=RuntimeError("API error"))
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A software invention",
        search_results=[],
        claims=[_make_claim()],
    )
    assert isinstance(result, AnalysisResult)
    assert len(result.findings) == 1
    assert result.findings[0].severity == AnalysisSeverity.HIGH
    desc_lower = result.findings[0].description.lower()
    assert "error" in desc_lower or "failed" in desc_lower


# ---------------------------------------------------------------------------
# Alice/Mayo two-step and statute
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finding_statute_is_101():
    llm = _make_llm(CONFLICT_RESPONSE)
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A software invention",
        search_results=[],
        claims=[_make_claim()],
    )
    assert "101" in result.findings[0].statute


@pytest.mark.asyncio
async def test_result_has_recommendation():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A physical device",
        search_results=[],
        claims=[_make_claim()],
    )
    assert result.recommendation
    assert isinstance(result.recommendation, str)


@pytest.mark.asyncio
async def test_system_prompt_mentions_alice_or_101():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    await analyzer.analyze(
        "A physical device",
        search_results=[],
        claims=[_make_claim()],
    )
    call_kwargs = llm.generate.call_args.kwargs if llm.generate.call_args.kwargs else {}
    system_arg = call_kwargs.get("system", "")
    if not system_arg:
        args = llm.generate.call_args[0]
        system_arg = args[1] if len(args) > 1 else ""
    assert system_arg
    lower = system_arg.lower()
    assert "101" in lower or "alice" in lower or "abstract" in lower or "eligible" in lower


@pytest.mark.asyncio
async def test_prompt_includes_claim_text():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = EligibilityAnalyzer(llm_provider=llm)
    claim_text = "A method of applying force to element Zeta via step Omega"
    await analyzer.analyze(
        "A physical device",
        search_results=[],
        claims=[_make_claim(text=claim_text)],
    )
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert claim_text in prompt
