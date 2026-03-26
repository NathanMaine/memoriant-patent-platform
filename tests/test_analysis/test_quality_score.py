"""Tests for core/analysis/quality_score.py — Patent Quality Scoring Service."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.llm.base import LLMProvider, LLMResponse
from core.models.application import DraftApplication, FilingFormat, Specification
from core.models.patent import Claim, SearchResult, SearchStrategy
from core.analysis.base import AnalysisResult, AnalysisStatus, AnalysisFinding, AnalysisSeverity
from core.analysis.quality_score import (
    QualityDimension,
    PatentQualityScore,
    PatentQualityScorer,
)


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


def _make_draft(
    title: str = "A novel widget",
    abstract: str = "A system and method for widgeting.",
    num_claims: int = 3,
) -> DraftApplication:
    claims = [
        Claim(number=1, type="independent", text="A method comprising: step A; step B."),
    ]
    if num_claims >= 2:
        claims.append(
            Claim(
                number=2,
                type="dependent",
                depends_on=1,
                text="The method of claim 1, wherein step A includes sub-step X.",
            )
        )
    if num_claims >= 3:
        claims.append(
            Claim(
                number=3,
                type="dependent",
                depends_on=1,
                text="The method of claim 1, wherein step B includes sub-step Y.",
            )
        )
    return DraftApplication(
        filing_format=FilingFormat.NONPROVISIONAL,
        title=title,
        abstract=abstract,
        specification=Specification(
            background="Background of the invention.",
            summary="Summary of the invention.",
            detailed_description="Detailed description with multiple embodiments.",
        ),
        claims=claims,
    )


def _make_analysis_result(
    module: str = "novelty",
    status: AnalysisStatus = AnalysisStatus.CLEAR,
) -> AnalysisResult:
    return AnalysisResult(
        module=module,
        status=status,
        findings=[
            AnalysisFinding(
                description="Sample finding.",
                severity=AnalysisSeverity.LOW,
                suggestion="No action needed.",
                statute="35 USC 102",
            )
        ],
        recommendation="Proceed.",
    )


# LLM response simulating all 6 scoring dimensions evaluated sequentially
_FULL_SCORE_RESPONSE = (
    "SCORE: 8.5\n"
    "NOTES: Claims are broad with appropriate fallback narrowing in dependent claims.\n"
    "STRENGTHS: Independent claim 1 is broad; dependent claims provide fallback positions.\n"
    "WEAKNESSES: Could add more fallback narrowing for step B.\n"
    "RECOMMENDATIONS: Add two more dependent claims narrowing step B."
)

_LOW_SCORE_RESPONSE = (
    "SCORE: 4.0\n"
    "NOTES: Claims are overly narrow and may lack commercial value.\n"
    "STRENGTHS: Clear claim language.\n"
    "WEAKNESSES: No independent broad claim; specification is thin.\n"
    "RECOMMENDATIONS: Broaden independent claim and add embodiments."
)


# ---------------------------------------------------------------------------
# Model tests — QualityDimension
# ---------------------------------------------------------------------------

def test_quality_dimension_instantiation():
    dim = QualityDimension(
        name="claim_breadth",
        score=8.0,
        weight=0.25,
        notes="Claims are broad.",
    )
    assert dim.name == "claim_breadth"
    assert dim.score == 8.0
    assert dim.weight == 0.25
    assert dim.notes == "Claims are broad."


def test_patent_quality_score_instantiation():
    score = PatentQualityScore(
        overall_score=85.0,
        grade="B",
        dimensions=[
            QualityDimension(name="claim_breadth", score=9.0, weight=0.25, notes="Good.")
        ],
        strengths=["Broad claims"],
        weaknesses=["Thin spec"],
        recommendations=["Add embodiments"],
    )
    assert score.overall_score == 85.0
    assert score.grade == "B"
    assert len(score.dimensions) == 1
    assert score.strengths == ["Broad claims"]
    assert score.weaknesses == ["Thin spec"]
    assert score.recommendations == ["Add embodiments"]


# ---------------------------------------------------------------------------
# Grade mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "overall_score,expected_grade",
    [
        (95.0, "A"),
        (90.0, "A"),
        (89.9, "B"),
        (80.0, "B"),
        (79.9, "C"),
        (70.0, "C"),
        (69.9, "D"),
        (60.0, "D"),
        (59.9, "F"),
        (0.0, "F"),
    ],
)
def test_grade_mapping(overall_score: float, expected_grade: str):
    scorer = PatentQualityScorer(llm_provider=_make_llm())
    grade = scorer._compute_grade(overall_score)
    assert grade == expected_grade


# ---------------------------------------------------------------------------
# score_draft — returns PatentQualityScore with all six dimensions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_draft_returns_patent_quality_score():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft())
    assert isinstance(result, PatentQualityScore)


@pytest.mark.asyncio
async def test_score_draft_returns_six_dimensions():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft())
    assert len(result.dimensions) == 6


@pytest.mark.asyncio
async def test_score_draft_dimension_names():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft())
    names = {d.name for d in result.dimensions}
    assert "claim_breadth" in names
    assert "specification_depth" in names
    assert "prior_art_differentiation" in names
    assert "formalities_compliance" in names
    assert "prosecution_readiness" in names
    assert "commercial_value" in names


@pytest.mark.asyncio
async def test_score_draft_dimension_weights_sum_to_one():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft())
    total_weight = sum(d.weight for d in result.dimensions)
    assert abs(total_weight - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# overall_score is the weighted average of dimension scores
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overall_score_is_weighted_average():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft())
    expected = sum(d.score * d.weight for d in result.dimensions) * 10.0
    assert abs(result.overall_score - expected) < 0.01


# ---------------------------------------------------------------------------
# overall_score bounds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overall_score_within_bounds():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft())
    assert 0.0 <= result.overall_score <= 100.0


# ---------------------------------------------------------------------------
# Grade is computed from overall_score
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grade_is_consistent_with_overall_score():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft())
    expected_grade = scorer._compute_grade(result.overall_score)
    assert result.grade == expected_grade


# ---------------------------------------------------------------------------
# Strengths and weaknesses are populated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_strengths_are_populated():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft())
    assert isinstance(result.strengths, list)
    assert len(result.strengths) >= 1


@pytest.mark.asyncio
async def test_weaknesses_are_populated():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft())
    assert isinstance(result.weaknesses, list)
    assert len(result.weaknesses) >= 1


@pytest.mark.asyncio
async def test_recommendations_are_populated():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft())
    assert isinstance(result.recommendations, list)
    assert len(result.recommendations) >= 1


# ---------------------------------------------------------------------------
# score_draft without analysis_results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_draft_without_analysis_results():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft(), analysis_results=None)
    assert isinstance(result, PatentQualityScore)
    assert len(result.dimensions) == 6


# ---------------------------------------------------------------------------
# score_draft with analysis_results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_draft_with_analysis_results():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    analysis = [
        _make_analysis_result("novelty", AnalysisStatus.CLEAR),
        _make_analysis_result("obviousness", AnalysisStatus.CAUTION),
    ]
    result = await scorer.score_draft(_make_draft(), analysis_results=analysis)
    assert isinstance(result, PatentQualityScore)
    assert len(result.dimensions) == 6


@pytest.mark.asyncio
async def test_score_draft_with_conflict_analysis_affects_score():
    """When prior analysis shows CONFLICT issues, score should tend lower than CLEAR."""
    # Use a low score response to simulate the LLM factoring in conflicts.
    llm_low = _make_llm(_LOW_SCORE_RESPONSE)
    scorer_low = PatentQualityScorer(llm_provider=llm_low)
    conflict_analysis = [
        _make_analysis_result("novelty", AnalysisStatus.CONFLICT),
        _make_analysis_result("obviousness", AnalysisStatus.CONFLICT),
    ]
    result_low = await scorer_low.score_draft(_make_draft(), analysis_results=conflict_analysis)

    llm_high = _make_llm(_FULL_SCORE_RESPONSE)
    scorer_high = PatentQualityScorer(llm_provider=llm_high)
    clear_analysis = [
        _make_analysis_result("novelty", AnalysisStatus.CLEAR),
        _make_analysis_result("obviousness", AnalysisStatus.CLEAR),
    ]
    result_high = await scorer_high.score_draft(_make_draft(), analysis_results=clear_analysis)

    assert result_low.overall_score < result_high.overall_score


# ---------------------------------------------------------------------------
# LLM is called once per dimension
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_called_once_per_dimension():
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    await scorer.score_draft(_make_draft())
    assert llm.generate.call_count == 6


# ---------------------------------------------------------------------------
# LLM error handling — graceful fallback score
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_error_returns_valid_score_object():
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=RuntimeError("API failure"))
    scorer = PatentQualityScorer(llm_provider=llm)
    result = await scorer.score_draft(_make_draft())
    assert isinstance(result, PatentQualityScore)
    assert 0.0 <= result.overall_score <= 100.0
    assert result.grade in {"A", "B", "C", "D", "F"}


# ---------------------------------------------------------------------------
# _safe_float — non-numeric string falls back to default
# ---------------------------------------------------------------------------

def test_safe_float_falls_back_on_invalid_string():
    from core.analysis.quality_score import _safe_float
    assert _safe_float("not-a-number", default=5.5) == 5.5


def test_safe_float_falls_back_on_none():
    from core.analysis.quality_score import _safe_float
    assert _safe_float(None, default=3.0) == 3.0  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Embodiments branch in context builder
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_draft_with_embodiments_in_specification():
    from core.models.application import Embodiment
    llm = _make_llm(_FULL_SCORE_RESPONSE)
    scorer = PatentQualityScorer(llm_provider=llm)
    draft = _make_draft()
    draft.specification.embodiments = [
        Embodiment(title="First embodiment", description="Embodiment A description."),
        Embodiment(title="Second embodiment", description="Embodiment B description."),
    ]
    result = await scorer.score_draft(draft)
    assert isinstance(result, PatentQualityScore)
    assert len(result.dimensions) == 6
