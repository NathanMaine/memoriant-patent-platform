"""Tests for core/analysis/claims.py — 35 USC 112(b) Definiteness analysis."""
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
from core.analysis.claims import ClaimsAnalyzer


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
    text: str = "A method comprising: receiving an input; processing said input.",
    claim_type: str = "independent",
) -> Claim:
    return Claim(number=number, type=claim_type, text=text)


def _make_dep_claim(number: int = 2, depends_on: int = 1) -> Claim:
    return Claim(
        number=number,
        type="dependent",
        text="The method of claim 1, further comprising outputting a result.",
        depends_on=depends_on,
    )


CLEAR_RESPONSE = (
    "INDEFINITE: No\n"
    "ISSUES: None identified\n"
    "ANTECEDENT_BASIS: Proper antecedent basis throughout\n"
    "SEVERITY: low\n"
    "SUGGESTION: Claims are definite as drafted.\n"
    "STATUS: clear"
)

CAUTION_RESPONSE = (
    "INDEFINITE: Possibly\n"
    "ISSUES: Term 'substantially' may be indefinite depending on context\n"
    "ANTECEDENT_BASIS: 'said device' in claim 2 lacks antecedent in claim 1\n"
    "SEVERITY: medium\n"
    "SUGGESTION: Define 'substantially' in the specification or replace with objective limits.\n"
    "STATUS: caution"
)

CONFLICT_RESPONSE = (
    "INDEFINITE: Yes\n"
    "ISSUES: Multiple terms are undefined; claim scope cannot be determined\n"
    "ANTECEDENT_BASIS: Several terms lack antecedent basis\n"
    "SEVERITY: high\n"
    "SUGGESTION: Claims must be substantially redrafted to meet 35 USC 112(b).\n"
    "STATUS: conflict"
)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_claims_analyzer_module_name():
    analyzer = ClaimsAnalyzer(llm_provider=_make_llm())
    assert analyzer.module_name == "claims"


def test_claims_analyzer_stores_provider():
    llm = _make_llm()
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    assert analyzer.llm_provider is llm


# ---------------------------------------------------------------------------
# Empty claims → CLEAR (no LLM call needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_claims_returns_clear():
    llm = _make_llm()
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[],
    )
    assert isinstance(result, AnalysisResult)
    assert result.module == "claims"
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_none_claims_returns_clear():
    llm = _make_llm()
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=None,
    )
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    llm.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Claims analysis ignores search_results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_claims_does_not_require_search_results():
    """ClaimsAnalyzer should work with empty search_results."""
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A novel device",
        search_results=[],
        claims=[_make_claim()],
    )
    assert isinstance(result, AnalysisResult)
    assert result.status == AnalysisStatus.CLEAR


# ---------------------------------------------------------------------------
# Status levels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clear_response():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A novel device",
        search_results=[],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CLEAR
    assert len(result.findings) == 1
    assert result.findings[0].severity == AnalysisSeverity.LOW


@pytest.mark.asyncio
async def test_caution_response():
    llm = _make_llm(CAUTION_RESPONSE)
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A novel device",
        search_results=[],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CAUTION
    assert result.findings[0].severity == AnalysisSeverity.MEDIUM


@pytest.mark.asyncio
async def test_conflict_response():
    llm = _make_llm(CONFLICT_RESPONSE)
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A novel device",
        search_results=[],
        claims=[_make_claim()],
    )
    assert result.status == AnalysisStatus.CONFLICT
    assert result.findings[0].severity == AnalysisSeverity.HIGH


# ---------------------------------------------------------------------------
# Multiple claims
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_claims_produce_findings():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    claims = [_make_claim(1), _make_dep_claim(2, 1)]
    result = await analyzer.analyze(
        "A novel device",
        search_results=[],
        claims=claims,
    )
    assert len(result.findings) == 2


@pytest.mark.asyncio
async def test_multiple_claims_worst_case():
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(
        side_effect=[
            LLMResponse(content=CLEAR_RESPONSE, model="mock", tokens_used=10),
            LLMResponse(content=CONFLICT_RESPONSE, model="mock", tokens_used=10),
        ]
    )
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A novel device",
        search_results=[],
        claims=[_make_claim(1), _make_dep_claim(2, 1)],
    )
    assert result.status == AnalysisStatus.CONFLICT


# ---------------------------------------------------------------------------
# LLM error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_error_handled_gracefully():
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=RuntimeError("Connection error"))
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A novel device",
        search_results=[],
        claims=[_make_claim()],
    )
    assert isinstance(result, AnalysisResult)
    assert len(result.findings) == 1
    assert result.findings[0].severity == AnalysisSeverity.HIGH
    desc_lower = result.findings[0].description.lower()
    assert "error" in desc_lower or "failed" in desc_lower


# ---------------------------------------------------------------------------
# Statute and structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finding_statute_is_112b():
    llm = _make_llm(CONFLICT_RESPONSE)
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A novel device",
        search_results=[],
        claims=[_make_claim()],
    )
    assert "112" in result.findings[0].statute


@pytest.mark.asyncio
async def test_result_has_recommendation():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "A novel device",
        search_results=[],
        claims=[_make_claim()],
    )
    assert result.recommendation
    assert isinstance(result.recommendation, str)


@pytest.mark.asyncio
async def test_prompt_includes_claim_text():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    claim_text = "A unique apparatus with element Z and component W"
    await analyzer.analyze(
        "A novel device",
        search_results=[],
        claims=[_make_claim(text=claim_text)],
    )
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert claim_text in prompt


@pytest.mark.asyncio
async def test_system_prompt_mentions_112_or_definiteness():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    await analyzer.analyze(
        "A novel device",
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
    assert "112" in lower or "definite" in lower or "indefinite" in lower


@pytest.mark.asyncio
async def test_specification_text_included_in_prompt_when_provided():
    """When specification is supplied, it must appear in the LLM prompt."""
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = ClaimsAnalyzer(llm_provider=llm)
    spec_text = "Detailed description of element W in the preferred embodiment."
    await analyzer.analyze(
        "A novel device",
        search_results=[],
        claims=[_make_claim()],
        specification=spec_text,
    )
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert spec_text in prompt
