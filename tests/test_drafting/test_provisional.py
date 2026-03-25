"""Tests for core/drafting/provisional.py — ProvisionalDrafter."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.llm.base import LLMProvider, LLMResponse
from core.models.patent import SearchResult, SearchStrategy
from core.models.application import DraftApplication, FilingFormat
from core.drafting.provisional import ProvisionalDrafter


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

# A realistic structured LLM response that the drafter should parse.
_MOCK_LLM_RESPONSE = """\
TITLE: Smart Widget with Adaptive Control System

ABSTRACT:
A smart widget comprising an adaptive control system configured to optimize
performance based on real-time sensor data. The system includes a processing
unit, a sensor array, and an adaptive algorithm that dynamically adjusts
operational parameters to maximize efficiency and user experience across
diverse environmental conditions. The invention enables unprecedented control
over widget functionality.

BACKGROUND:
Prior art widgets lacked adaptive control mechanisms, relying on static
parameter sets that could not respond to changing conditions. Existing systems
required manual recalibration, resulting in suboptimal performance and user
frustration.

SUMMARY:
The present invention provides a smart widget with an adaptive control system
that automatically optimizes performance using real-time sensor feedback and
machine learning algorithms, eliminating the need for manual recalibration.

DETAILED_DESCRIPTION:
The smart widget comprises a housing containing a processing unit operatively
connected to a sensor array. The processing unit executes an adaptive algorithm
that receives sensor inputs and computes optimal operational parameters. The
sensor array includes temperature, pressure, and motion sensors. The adaptive
algorithm uses gradient descent optimization to minimize a loss function
representing deviation from target performance metrics.

EMBODIMENT 1:
Title: Portable Consumer Device Implementation
Description: In a first embodiment, the smart widget is implemented as a
portable consumer device with a rechargeable battery. The sensor array is
miniaturized to fit within a compact form factor. The processing unit is a
low-power ARM-based microcontroller. The adaptive algorithm runs continuously
in the background, adjusting settings without user intervention.

EMBODIMENT 2:
Title: Industrial Automation Implementation
Description: In a second embodiment, the smart widget is deployed in an
industrial automation context. The sensor array includes additional industrial
sensors for monitoring equipment health. The processing unit is a ruggedized
industrial computer capable of operating in extreme temperatures.

CLAIM 1 (independent):
A smart widget comprising: a housing; a processing unit disposed within the
housing; a sensor array operatively connected to the processing unit; and an
adaptive control system configured to receive sensor data from the sensor array
and dynamically adjust operational parameters of the smart widget based on
the received sensor data.

CLAIM 2 (dependent on 1):
The smart widget of claim 1, wherein the adaptive control system comprises a
machine learning algorithm trained to optimize a performance metric.

CLAIM 3 (dependent on 1):
The smart widget of claim 1, wherein the sensor array comprises at least one
of a temperature sensor, a pressure sensor, and a motion sensor.
"""


def _make_llm(response_text: str = _MOCK_LLM_RESPONSE) -> LLMProvider:
    provider = MagicMock(spec=LLMProvider)
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content=response_text,
            model="mock-model",
            tokens_used=500,
        )
    )
    return provider


def _make_search_result(patent_id: str = "US1234567", title: str = "Prior Art Widget") -> SearchResult:
    return SearchResult(
        patent_id=patent_id,
        title=title,
        abstract="A static widget without adaptive control.",
        provider="mock",
        strategy=SearchStrategy.KEYWORD,
    )


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_provisional_drafter_instantiation():
    """ProvisionalDrafter can be constructed with an LLMProvider."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    assert drafter is not None
    assert drafter.llm_provider is llm


# ---------------------------------------------------------------------------
# Filing format
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_draft_application_type():
    """draft() returns a DraftApplication instance."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.")
    assert isinstance(result, DraftApplication)


@pytest.mark.asyncio
async def test_filing_format_is_provisional():
    """Returned DraftApplication has filing_format == 'provisional'."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.")
    assert result.filing_format == FilingFormat.PROVISIONAL


# ---------------------------------------------------------------------------
# Abstract constraints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_abstract_is_150_words_or_fewer():
    """Abstract must be 150 words or fewer per USPTO rules."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.")
    assert result.abstract is not None
    word_count = len(result.abstract.split())
    assert word_count <= 150, f"Abstract has {word_count} words, expected ≤ 150"


# ---------------------------------------------------------------------------
# Specification completeness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_specification_background_non_empty():
    """Specification must have a non-empty background section."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.")
    assert result.specification.background
    assert len(result.specification.background.strip()) > 0


@pytest.mark.asyncio
async def test_specification_summary_non_empty():
    """Specification must have a non-empty summary section."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.")
    assert result.specification.summary
    assert len(result.specification.summary.strip()) > 0


@pytest.mark.asyncio
async def test_specification_detailed_description_non_empty():
    """Specification must have a non-empty detailed_description section."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.")
    assert result.specification.detailed_description
    assert len(result.specification.detailed_description.strip()) > 0


@pytest.mark.asyncio
async def test_at_least_one_embodiment():
    """Specification must contain at least one embodiment."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.")
    assert len(result.specification.embodiments) >= 1


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_at_least_one_independent_claim():
    """Draft must include at least one independent claim."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.")
    independent_claims = [c for c in result.claims if c.type == "independent"]
    assert len(independent_claims) >= 1


# ---------------------------------------------------------------------------
# Filing checklist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filing_checklist_contains_required_items():
    """Filing checklist must contain the required USPTO items."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.")
    checklist = result.ads_data.get("filing_checklist", [])
    assert any("PTO/SB/16" in item or "Cover sheet" in item for item in checklist)
    assert any("Filing fee" in item for item in checklist)
    assert any("Specification" in item for item in checklist)


# ---------------------------------------------------------------------------
# Prior art handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_draft_without_prior_art():
    """draft() succeeds without providing prior art results."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.", prior_art_results=None)
    assert isinstance(result, DraftApplication)
    assert result.filing_format == FilingFormat.PROVISIONAL


@pytest.mark.asyncio
async def test_draft_with_prior_art_includes_context_in_prompt():
    """Prior art results are included in the LLM prompt."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    prior_art = [_make_search_result("US9876543", "Existing Widget")]
    await drafter.draft("A smart widget with adaptive control.", prior_art_results=prior_art)
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "US9876543" in prompt or "Existing Widget" in prompt


@pytest.mark.asyncio
async def test_draft_with_empty_prior_art_list():
    """draft() succeeds with an empty list of prior art results."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.", prior_art_results=[])
    assert isinstance(result, DraftApplication)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preferences_passed_to_llm_prompt():
    """User preferences are reflected in the LLM prompt."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    prefs = {"claim_breadth": "broad", "num_embodiments": 3}
    await drafter.draft("A smart widget with adaptive control.", preferences=prefs)
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "broad" in prompt or "3" in prompt


@pytest.mark.asyncio
async def test_default_preferences_when_none_provided():
    """draft() works correctly when no preferences are provided."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.", preferences=None)
    assert isinstance(result, DraftApplication)
    # LLM should still have been called once with a valid prompt
    llm.generate.assert_called_once()


# ---------------------------------------------------------------------------
# LLM error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_error_returns_partial_result():
    """LLM failure returns a graceful partial result with error metadata."""
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=RuntimeError("LLM connection failed"))
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget with adaptive control.")
    # Should return a DraftApplication (not raise), with error info in ads_data
    assert isinstance(result, DraftApplication)
    assert result.filing_format == FilingFormat.PROVISIONAL
    ads = result.ads_data or {}
    assert ads.get("error") is not None


# ---------------------------------------------------------------------------
# Coverage gap: prior art with relevance_score / relevance_notes in prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prior_art_with_relevance_score_and_notes_in_prompt():
    """Prior art relevance_score and relevance_notes are included in the prompt."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    prior_art = [
        SearchResult(
            patent_id="US7654321",
            title="Scored Prior Art",
            abstract="An abstract about prior widgets.",
            relevance_score=0.92,
            relevance_notes="Highly relevant to claim 1",
            provider="mock",
            strategy=SearchStrategy.KEYWORD,
        )
    ]
    await drafter.draft("A smart widget.", prior_art_results=prior_art)
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "0.92" in prompt
    assert "Highly relevant" in prompt


# ---------------------------------------------------------------------------
# Coverage gap: abstract truncation to ≤150 words
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_abstract_truncated_when_llm_returns_over_150_words():
    """Abstracts longer than 150 words are truncated to exactly 150 words."""
    # Build a response with a deliberately long abstract (200 words)
    long_abstract_words = " ".join(["word"] * 200)
    long_response = _MOCK_LLM_RESPONSE.replace(
        "ABSTRACT:\nA smart widget comprising an adaptive control system configured to optimize\n"
        "performance based on real-time sensor data. The system includes a processing\n"
        "unit, a sensor array, and an adaptive algorithm that dynamically adjusts\n"
        "operational parameters to maximize efficiency and user experience across\n"
        "diverse environmental conditions. The invention enables unprecedented control\n"
        "over widget functionality.",
        f"ABSTRACT:\n{long_abstract_words}",
    )
    llm = _make_llm(long_response)
    drafter = ProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("A smart widget.")
    assert result.abstract is not None
    assert len(result.abstract.split()) <= 150


# ---------------------------------------------------------------------------
# Coverage gap: extra/unknown preference keys are forwarded to prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_preference_keys_forwarded_to_prompt():
    """Preference keys beyond claim_breadth and num_embodiments appear in prompt."""
    llm = _make_llm()
    drafter = ProvisionalDrafter(llm_provider=llm)
    prefs = {
        "claim_breadth": "moderate",
        "num_embodiments": 2,
        "jurisdiction": "US",
        "language": "plain",
    }
    await drafter.draft("A smart widget.", preferences=prefs)
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "jurisdiction" in prompt
    assert "language" in prompt
