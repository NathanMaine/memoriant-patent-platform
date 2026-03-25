"""Tests for core/analysis/specification.py — 35 USC 112(a) enablement/written description."""
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
from core.analysis.specification import SpecificationAnalyzer


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


def _make_claim(number: int = 1, text: str = "A method comprising: step A; step B.") -> Claim:
    return Claim(number=number, type="independent", text=text)


SAMPLE_SPEC = (
    "The present invention relates to a method for processing data. "
    "Step A involves receiving data from an external source. "
    "Step B involves transforming the data using a novel algorithm described herein. "
    "A person of ordinary skill in the art would be able to perform the claimed steps "
    "based on the detailed description provided."
)

CLEAR_RESPONSE = (
    "ENABLEMENT: Yes\n"
    "WRITTEN_DESCRIPTION: Supported\n"
    "ISSUES: None\n"
    "SEVERITY: low\n"
    "SUGGESTION: Specification adequately supports the claims.\n"
    "STATUS: clear"
)

CAUTION_RESPONSE = (
    "ENABLEMENT: Possibly\n"
    "WRITTEN_DESCRIPTION: Partially supported\n"
    "ISSUES: Claim 1 element C not fully described in spec\n"
    "SEVERITY: medium\n"
    "SUGGESTION: Add additional disclosure for element C to ensure enablement.\n"
    "STATUS: caution"
)

CONFLICT_RESPONSE = (
    "ENABLEMENT: No\n"
    "WRITTEN_DESCRIPTION: Not supported\n"
    "ISSUES: Claims broadly cover unexemplified embodiments; undue experimentation required\n"
    "SEVERITY: high\n"
    "SUGGESTION: Narrow claims or substantially expand the specification.\n"
    "STATUS: conflict"
)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_specification_analyzer_module_name():
    analyzer = SpecificationAnalyzer(llm_provider=_make_llm())
    assert analyzer.module_name == "specification"


def test_specification_analyzer_stores_provider():
    llm = _make_llm()
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    assert analyzer.llm_provider is llm


# ---------------------------------------------------------------------------
# Empty inputs → CLEAR
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_claims_returns_clear():
    llm = _make_llm()
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[],
        specification=SAMPLE_SPEC,
    )
    assert isinstance(result, AnalysisResult)
    assert result.module == "specification"
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_none_claims_returns_clear():
    llm = _make_llm()
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=None,
        specification=SAMPLE_SPEC,
    )
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    llm.generate.assert_not_called()


@pytest.mark.asyncio
async def test_no_specification_returns_clear():
    """Without a specification text, there is nothing to analyze."""
    llm = _make_llm()
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[_make_claim()],
        specification=None,
    )
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    llm.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Status levels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clear_response():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[_make_claim()],
        specification=SAMPLE_SPEC,
    )
    assert result.status == AnalysisStatus.CLEAR
    assert len(result.findings) == 1
    assert result.findings[0].severity == AnalysisSeverity.LOW


@pytest.mark.asyncio
async def test_caution_response():
    llm = _make_llm(CAUTION_RESPONSE)
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[_make_claim()],
        specification=SAMPLE_SPEC,
    )
    assert result.status == AnalysisStatus.CAUTION
    assert result.findings[0].severity == AnalysisSeverity.MEDIUM


@pytest.mark.asyncio
async def test_conflict_response():
    llm = _make_llm(CONFLICT_RESPONSE)
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[_make_claim()],
        specification=SAMPLE_SPEC,
    )
    assert result.status == AnalysisStatus.CONFLICT
    assert result.findings[0].severity == AnalysisSeverity.HIGH


# ---------------------------------------------------------------------------
# Multiple claims
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_claims_produce_findings():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[_make_claim(1), _make_claim(2, "An apparatus comprising component X.")],
        specification=SAMPLE_SPEC,
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
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[_make_claim(1), _make_claim(2, "An apparatus comprising component X.")],
        specification=SAMPLE_SPEC,
    )
    assert result.status == AnalysisStatus.CONFLICT


# ---------------------------------------------------------------------------
# LLM error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_error_handled_gracefully():
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=RuntimeError("Server error"))
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[_make_claim()],
        specification=SAMPLE_SPEC,
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
async def test_finding_statute_is_112a():
    llm = _make_llm(CONFLICT_RESPONSE)
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[_make_claim()],
        specification=SAMPLE_SPEC,
    )
    assert "112" in result.findings[0].statute


@pytest.mark.asyncio
async def test_result_has_recommendation():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    result = await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[_make_claim()],
        specification=SAMPLE_SPEC,
    )
    assert result.recommendation
    assert isinstance(result.recommendation, str)


@pytest.mark.asyncio
async def test_prompt_includes_specification_text():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    spec = "Unique specification content with element delta"
    await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[_make_claim()],
        specification=spec,
    )
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert spec in prompt


@pytest.mark.asyncio
async def test_system_prompt_mentions_enablement_or_112():
    llm = _make_llm(CLEAR_RESPONSE)
    analyzer = SpecificationAnalyzer(llm_provider=llm)
    await analyzer.analyze(
        "An invention description",
        search_results=[],
        claims=[_make_claim()],
        specification=SAMPLE_SPEC,
    )
    call_kwargs = llm.generate.call_args.kwargs if llm.generate.call_args.kwargs else {}
    system_arg = call_kwargs.get("system", "")
    if not system_arg:
        args = llm.generate.call_args[0]
        system_arg = args[1] if len(args) > 1 else ""
    assert system_arg
    lower = system_arg.lower()
    assert "112" in lower or "enablement" in lower or "written description" in lower
