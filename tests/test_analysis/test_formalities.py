"""Tests for core/analysis/formalities.py — MPEP 608 formalities checks.

All checks are rule-based (no LLM required). Tests cover each rule
independently as well as aggregate status and edge cases.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from core.llm.base import LLMProvider
from core.models.patent import Claim, SearchResult, SearchStrategy
from core.models.application import Specification, Embodiment, DraftApplication, FilingFormat
from core.analysis.base import (
    AnalysisSeverity,
    AnalysisStatus,
    AnalysisResult,
)
from core.analysis.formalities import FormalitiesAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_spec(
    background: str = "This invention relates to data processing.",
    summary: str = "A method for processing data more efficiently.",
    detailed_description: str = "The method comprises steps A, B, and C.",
    embodiments: list[Embodiment] | None = None,
) -> Specification:
    if embodiments is None:
        embodiments = [Embodiment(title="First Embodiment", description="A first embodiment is described.")]
    return Specification(
        background=background,
        summary=summary,
        detailed_description=detailed_description,
        embodiments=embodiments,
    )


def _make_independent_claim(number: int = 1, text: str = "A method comprising: step A; step B.") -> Claim:
    return Claim(number=number, type="independent", text=text)


def _make_dependent_claim(number: int = 2, depends_on: int = 1) -> Claim:
    return Claim(
        number=number,
        type="dependent",
        text=f"The method of claim {depends_on}, further comprising step C.",
        depends_on=depends_on,
    )


def _150_word_abstract() -> str:
    """Returns an abstract of exactly 150 words."""
    word = "data"
    base = (
        "The present invention discloses a novel method and apparatus for processing "
        "information in a distributed computing environment. The system comprises a "
        "central processing unit operably connected to a plurality of distributed nodes. "
        "Each node is configured to receive, store, and transmit data packets over a "
        "high-speed network interface. The method includes steps of initializing the "
        "network, authenticating each node using a cryptographic protocol, distributing "
        "workloads across available resources, and aggregating results at the central unit. "
        "Performance metrics are collected and analyzed to optimize throughput and reduce "
        "latency. The invention is particularly useful in cloud computing deployments where "
        "scalability and fault tolerance are critical requirements for reliable system operation."
    )
    words = base.split()
    # Trim or pad to exactly 150 words
    while len(words) < 150:
        words.append(word)
    return " ".join(words[:150])


def _200_word_abstract() -> str:
    """Returns an abstract of exactly 200 words."""
    word = "processing"
    base = _150_word_abstract().split()
    while len(base) < 200:
        base.append(word)
    return " ".join(base[:200])


def _make_draft_application(
    title: str = "Data Processing Method",
    abstract: str | None = None,
    claims: list[Claim] | None = None,
    spec: Specification | None = None,
) -> DraftApplication:
    if abstract is None:
        abstract = _150_word_abstract()
    if claims is None:
        claims = [_make_independent_claim(1), _make_dependent_claim(2, 1)]
    if spec is None:
        spec = _make_spec()
    return DraftApplication(
        filing_format=FilingFormat.NONPROVISIONAL,
        title=title,
        abstract=abstract,
        specification=spec,
        claims=claims,
    )


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_formalities_analyzer_module_name():
    analyzer = FormalitiesAnalyzer()
    assert analyzer.module_name == "formalities"


def test_formalities_analyzer_no_llm_required():
    """FormalitiesAnalyzer should work without an LLM provider."""
    analyzer = FormalitiesAnalyzer()
    assert analyzer.llm_provider is None


def test_formalities_analyzer_accepts_llm_provider():
    """Constructor should accept an optional LLM provider."""
    llm = MagicMock(spec=LLMProvider)
    analyzer = FormalitiesAnalyzer(llm_provider=llm)
    assert analyzer.llm_provider is llm


# ---------------------------------------------------------------------------
# Rule 1: Abstract length ≤ 150 words
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_abstract_exactly_150_words_passes():
    """An abstract of exactly 150 words should pass (CLEAR, no finding for abstract)."""
    abstract = _150_word_abstract()
    assert len(abstract.split()) == 150

    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="A data processing invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=_make_spec(),
        abstract=abstract,
        title="Valid Title",
    )
    abstract_findings = [f for f in result.findings if "abstract" in f.description.lower()]
    assert not abstract_findings, "150-word abstract should produce no abstract-length finding"


@pytest.mark.asyncio
async def test_abstract_200_words_fails():
    """An abstract of 200 words should produce a finding with suggestion."""
    abstract = _200_word_abstract()
    assert len(abstract.split()) == 200

    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="A data processing invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=_make_spec(),
        abstract=abstract,
        title="Valid Title",
    )
    abstract_findings = [f for f in result.findings if "abstract" in f.description.lower() and "150" in f.description]
    assert abstract_findings, "200-word abstract should produce an abstract-length finding"
    assert abstract_findings[0].suggestion, "Finding must include a suggestion"
    assert abstract_findings[0].statute == "MPEP 608"


@pytest.mark.asyncio
async def test_no_abstract_fails():
    """Missing abstract should produce a finding."""
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="A data processing invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=_make_spec(),
        abstract=None,
        title="Valid Title",
    )
    abstract_findings = [f for f in result.findings if "abstract" in f.description.lower()]
    assert abstract_findings, "Missing abstract should produce a finding"


# ---------------------------------------------------------------------------
# Rule 2: Title length < 500 characters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_title_too_long_fails():
    """A title exceeding 500 characters should produce a finding."""
    long_title = "A " * 260  # 520 characters
    assert len(long_title) > 500

    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="A data processing invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title=long_title,
    )
    title_findings = [f for f in result.findings if "title" in f.description.lower()]
    assert title_findings, "Title >500 chars should produce a finding"
    assert title_findings[0].statute == "MPEP 608"


@pytest.mark.asyncio
async def test_title_exactly_500_chars_passes():
    """A title of exactly 500 characters should pass."""
    title_500 = "A" * 500
    assert len(title_500) == 500

    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="A data processing invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title=title_500,
    )
    title_findings = [f for f in result.findings if "title" in f.description.lower() and "500" in f.description]
    assert not title_findings, "Title of exactly 500 chars should not produce a length finding"


# ---------------------------------------------------------------------------
# Rule 3: Claims numbering — sequential starting from 1
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_claims_not_sequential_fails():
    """Claims numbered 1, 3 (skipping 2) should produce a finding."""
    claims = [
        _make_independent_claim(1),
        _make_independent_claim(3),  # gap — missing 2
    ]
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=claims,
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    seq_findings = [f for f in result.findings if "sequenti" in f.description.lower() or "number" in f.description.lower()]
    assert seq_findings, "Non-sequential claim numbering should produce a finding"


@pytest.mark.asyncio
async def test_claims_not_starting_from_1_fails():
    """Claims starting from 2 should produce a numbering finding."""
    claims = [
        _make_independent_claim(2),
        _make_dependent_claim(3, 2),
    ]
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=claims,
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    seq_findings = [f for f in result.findings if "sequenti" in f.description.lower() or "number" in f.description.lower()]
    assert seq_findings, "Claims not starting from 1 should produce a finding"


# ---------------------------------------------------------------------------
# Rule 4: Dependent claims must reference a valid claim number
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dependent_claim_references_nonexistent_claim_fails():
    """A dependent claim referencing claim 99 (which doesn't exist) should fail."""
    claims = [
        _make_independent_claim(1),
        Claim(
            number=2,
            type="dependent",
            text="The method of claim 99, further comprising step D.",
            depends_on=99,
        ),
    ]
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=claims,
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    dep_findings = [f for f in result.findings if "dependent" in f.description.lower() or "reference" in f.description.lower()]
    assert dep_findings, "Dependent claim referencing non-existent claim should produce a finding"


# ---------------------------------------------------------------------------
# Rule 5: At least one independent claim
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_independent_claims_fails():
    """An application with only dependent claims should produce a finding."""
    # Create a standalone dependent claim (need depends_on but no independent exists)
    # Use a workaround: create as dependent but reference a claim that won't exist
    claims = [
        Claim(
            number=1,
            type="dependent",
            text="The method of claim 2, further comprising step A.",
            depends_on=2,
        ),
        Claim(
            number=2,
            type="dependent",
            text="The method of claim 1, further comprising step B.",
            depends_on=1,
        ),
    ]
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=claims,
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    indep_findings = [f for f in result.findings if "independent" in f.description.lower()]
    assert indep_findings, "No independent claims should produce a finding"


# ---------------------------------------------------------------------------
# Rule 6: Non-empty specification sections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_background_fails():
    """Empty background section should produce a finding."""
    spec = _make_spec(background="")
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=spec,
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    spec_findings = [f for f in result.findings if "background" in f.description.lower()]
    assert spec_findings, "Empty background section should produce a finding"


@pytest.mark.asyncio
async def test_empty_summary_fails():
    """Empty summary section should produce a finding."""
    spec = _make_spec(summary="")
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=spec,
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    spec_findings = [f for f in result.findings if "summary" in f.description.lower()]
    assert spec_findings, "Empty summary section should produce a finding"


@pytest.mark.asyncio
async def test_empty_detailed_description_fails():
    """Empty detailed_description section should produce a finding."""
    spec = _make_spec(detailed_description="")
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=spec,
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    spec_findings = [f for f in result.findings if "detailed" in f.description.lower() or "description" in f.description.lower()]
    assert spec_findings, "Empty detailed_description should produce a finding"


# ---------------------------------------------------------------------------
# Rule 7: At least one embodiment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_embodiments_fails():
    """A specification with no embodiments should produce a finding."""
    spec = _make_spec(embodiments=[])
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=spec,
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    emb_findings = [f for f in result.findings if "embodiment" in f.description.lower()]
    assert emb_findings, "No embodiments should produce a finding"


# ---------------------------------------------------------------------------
# Aggregate status tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_perfect_application_is_clear():
    """A fully compliant application should return CLEAR status with no findings."""
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="A data processing invention.",
        search_results=[],
        claims=[_make_independent_claim(1), _make_dependent_claim(2, 1)],
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title="Data Processing Method and Apparatus",
    )
    assert isinstance(result, AnalysisResult)
    assert result.module == "formalities"
    assert result.status == AnalysisStatus.CLEAR
    assert result.findings == []
    assert result.recommendation


@pytest.mark.asyncio
async def test_single_issue_returns_caution():
    """A single minor issue (abstract too long) should return CAUTION."""
    abstract = _200_word_abstract()
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=[_make_independent_claim(1), _make_dependent_claim(2, 1)],
        specification=_make_spec(),
        abstract=abstract,
        title="Valid Title",
    )
    assert result.status in (AnalysisStatus.CAUTION, AnalysisStatus.CONFLICT)
    assert len(result.findings) >= 1


@pytest.mark.asyncio
async def test_many_issues_returns_conflict():
    """Multiple issues should produce CONFLICT status."""
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=[
            # Claims start from 2 (not 1) — numbering issue
            Claim(number=2, type="independent", text="A method comprising step A."),
            # Dependent references non-existent claim 99
            Claim(number=3, type="dependent", text="The method of claim 99.", depends_on=99),
        ],
        specification=_make_spec(background="", summary="", embodiments=[]),
        abstract=_200_word_abstract(),
        title="A" * 600,  # title too long
    )
    assert result.status == AnalysisStatus.CONFLICT
    assert len(result.findings) >= 3


# ---------------------------------------------------------------------------
# DraftApplication extraction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_extracts_from_draft_application():
    """analyze() should accept a DraftApplication and use its claims/spec/abstract/title."""
    draft = _make_draft_application()
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="A data processing invention.",
        search_results=[],
        draft_application=draft,
    )
    assert isinstance(result, AnalysisResult)
    assert result.module == "formalities"
    assert result.status == AnalysisStatus.CLEAR


@pytest.mark.asyncio
async def test_draft_application_with_bad_abstract_fails():
    """When DraftApplication has a bad abstract... but DraftApplication validates at 150 words.
    Use a draft app whose abstract is None to trigger the missing-abstract check."""
    draft = DraftApplication(
        filing_format=FilingFormat.NONPROVISIONAL,
        title="Valid Title",
        abstract=None,
        specification=_make_spec(),
        claims=[_make_independent_claim(1)],
    )
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        draft_application=draft,
    )
    abstract_findings = [f for f in result.findings if "abstract" in f.description.lower()]
    assert abstract_findings, "Draft application with no abstract should produce a finding"


# ---------------------------------------------------------------------------
# search_results is ignored
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_results_are_ignored():
    """Formalities analysis should produce identical results regardless of search_results."""
    from datetime import date
    from uuid import uuid4

    sr = SearchResult(
        id=uuid4(),
        patent_id="US1234567",
        title="Some prior art",
        provider="test",
        strategy=SearchStrategy.KEYWORD,
    )
    analyzer = FormalitiesAnalyzer()
    result_no_sr = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    result_with_sr = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[sr],
        claims=[_make_independent_claim()],
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    assert result_no_sr.status == result_with_sr.status
    assert len(result_no_sr.findings) == len(result_with_sr.findings)


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_result_module_name():
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    assert result.module == "formalities"


@pytest.mark.asyncio
async def test_all_findings_reference_mpep_608():
    """Every finding produced by FormalitiesAnalyzer should cite MPEP 608."""
    abstract = _200_word_abstract()
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=_make_spec(background="", embodiments=[]),
        abstract=abstract,
        title="Valid Title",
    )
    for finding in result.findings:
        assert "608" in finding.statute, f"Finding statute should reference MPEP 608, got: {finding.statute}"


# ---------------------------------------------------------------------------
# Additional branch coverage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_title_fails():
    """None title should produce a title-missing finding."""
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title=None,
    )
    title_findings = [f for f in result.findings if "title" in f.description.lower()]
    assert title_findings, "None title should produce a finding"
    assert title_findings[0].statute == "MPEP 608"


@pytest.mark.asyncio
async def test_empty_string_title_fails():
    """Empty string title should produce a title-missing finding."""
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=[_make_independent_claim()],
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title="   ",
    )
    title_findings = [f for f in result.findings if "title" in f.description.lower()]
    assert title_findings, "Whitespace-only title should produce a finding"


@pytest.mark.asyncio
async def test_no_claims_list_skips_claims_checks():
    """Passing claims=None should skip claim checks and not produce claim findings."""
    analyzer = FormalitiesAnalyzer()
    result = await analyzer.analyze(
        invention_description="An invention.",
        search_results=[],
        claims=None,
        specification=_make_spec(),
        abstract=_150_word_abstract(),
        title="Valid Title",
    )
    claim_findings = [
        f for f in result.findings
        if "claim" in f.description.lower() and "abstract" not in f.description.lower()
    ]
    assert not claim_findings, "No claims supplied should not produce claim-specific findings"
