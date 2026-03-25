"""Tests for core/drafting/nonprovisional.py — NonProvisionalDrafter."""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.llm.base import LLMProvider, LLMResponse
from core.models.application import DraftApplication, FilingFormat
from core.models.patent import SearchResult, SearchStrategy
from core.drafting.nonprovisional import NonProvisionalDrafter


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_MOCK_LLM_RESPONSE = """\
TITLE: Advanced Widget System with Multi-Mode Operation

ABSTRACT:
An advanced widget system comprising a multi-mode operation controller
configured to switch between operational modes based on environmental
inputs. The system includes a primary processing unit, a sensor fusion
module, and a layered control architecture that enables dynamic mode
selection and parameter optimization. The invention provides improved
performance and flexibility for both consumer and industrial applications
in diverse operating environments.

BACKGROUND:
Prior art widget systems were limited to single-mode operation, preventing
optimal performance across varying environmental conditions. Existing
systems required complete replacement when operational requirements changed.

SUMMARY:
The present invention provides an advanced widget system with multi-mode
operation that dynamically selects and optimizes operational parameters
based on real-time environmental sensing, enabling a single system to
serve multiple operational contexts.

DETAILED_DESCRIPTION:
The advanced widget system comprises a housing enclosing a primary processing
unit operatively connected to a sensor fusion module. The multi-mode
operation controller receives sensor data and applies decision logic to
select among a plurality of operational modes. Each mode is defined by a
parameter set optimized for a specific operational context.

EMBODIMENT 1:
Title: Consumer Electronics Implementation
Description: In a first embodiment, the advanced widget system is implemented
as a consumer electronics device with wireless connectivity. The sensor
fusion module integrates accelerometer, gyroscope, and proximity sensors.
The multi-mode controller automatically transitions between home, office,
and outdoor modes.

EMBODIMENT 2:
Title: Industrial Automation Platform
Description: In a second embodiment, the advanced widget system serves as
an industrial automation platform. The sensor fusion module includes
vibration, temperature, and current sensors. The system supports
predictive maintenance mode in addition to standard operational modes.

EMBODIMENT 3:
Title: Medical Device Configuration
Description: In a third embodiment, the advanced widget system is configured
as a medical monitoring device. Sensor fusion includes biometric sensors.
The multi-mode controller enforces regulatory-compliant operational
constraints in medical and non-medical contexts.

CLAIM 1 (independent):
An advanced widget system comprising: a housing; a primary processing unit
disposed within the housing; a sensor fusion module operatively coupled to
the primary processing unit and configured to aggregate data from a
plurality of sensors; and a multi-mode operation controller configured to
select an operational mode from a plurality of predefined operational modes
based on the aggregated sensor data.

CLAIM 2 (dependent on 1):
The advanced widget system of claim 1, wherein the plurality of predefined
operational modes includes at least a first mode optimized for low-power
consumption and a second mode optimized for high-performance output.

CLAIM 3 (dependent on 1):
The advanced widget system of claim 1, wherein the sensor fusion module
comprises at least one of an accelerometer, a gyroscope, a temperature
sensor, and a proximity sensor.

CLAIM 4 (dependent on 2):
The advanced widget system of claim 2, wherein transitioning between the
first mode and the second mode is triggered by a threshold crossing event
detected by the sensor fusion module.
"""

_MINIMAL_LLM_RESPONSE = """\
TITLE: Basic Device

ABSTRACT:
A basic device for performing operations.

BACKGROUND:
Prior art lacks basic devices.

SUMMARY:
This invention provides a basic device.

DETAILED_DESCRIPTION:
The basic device comprises a housing with internal components.

EMBODIMENT 1:
Title: Standard Configuration
Description: A standard configuration of the basic device.

EMBODIMENT 2:
Title: Enhanced Configuration
Description: An enhanced configuration with additional features.

EMBODIMENT 3:
Title: Compact Configuration
Description: A compact form factor for portable use.

CLAIM 1 (independent):
A basic device comprising a housing and one or more internal components.

CLAIM 2 (dependent on 1):
The basic device of claim 1, wherein the internal components include a processor.

CLAIM 3 (dependent on 1):
The basic device of claim 1, wherein the housing is weather-resistant.
"""


def _make_llm(response_text: str = _MOCK_LLM_RESPONSE) -> LLMProvider:
    provider = MagicMock(spec=LLMProvider)
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content=response_text,
            model="mock-model",
            tokens_used=800,
        )
    )
    return provider


def _make_search_result(patent_id: str = "US1234567", title: str = "Prior Art Widget") -> SearchResult:
    return SearchResult(
        patent_id=patent_id,
        title=title,
        abstract="A static widget without multi-mode control.",
        provider="mock",
        strategy=SearchStrategy.KEYWORD,
    )


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_nonprovisional_drafter_instantiation():
    """NonProvisionalDrafter can be constructed with an LLMProvider."""
    llm = _make_llm()
    drafter = NonProvisionalDrafter(llm_provider=llm)
    assert drafter is not None
    assert drafter.llm_provider is llm


# ---------------------------------------------------------------------------
# Filing format
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_draft_application_type():
    """draft() returns a DraftApplication instance."""
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An advanced widget system.")
    assert isinstance(result, DraftApplication)


@pytest.mark.asyncio
async def test_filing_format_is_nonprovisional():
    """Returned DraftApplication has filing_format == 'nonprovisional'."""
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An advanced widget system.")
    assert result.filing_format == FilingFormat.NONPROVISIONAL


# ---------------------------------------------------------------------------
# Embodiments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generates_at_least_three_embodiments_by_default():
    """draft() generates at least 3 embodiments by default."""
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An advanced widget system.")
    assert len(result.specification.embodiments) >= 3


@pytest.mark.asyncio
async def test_num_embodiments_preference_forwarded_to_prompt():
    """preferences.num_embodiments is included in the LLM prompt."""
    llm = _make_llm()
    drafter = NonProvisionalDrafter(llm_provider=llm)
    await drafter.draft("An advanced widget system.", preferences={"num_embodiments": 5})
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "5" in prompt


# ---------------------------------------------------------------------------
# Claims — independent AND dependent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_independent_claims():
    """Draft must include at least one independent claim."""
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An advanced widget system.")
    independent = [c for c in result.claims if c.type == "independent"]
    assert len(independent) >= 1


@pytest.mark.asyncio
async def test_has_dependent_claims():
    """Draft must include at least one dependent claim (layered fallback)."""
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An advanced widget system.")
    dependent = [c for c in result.claims if c.type == "dependent"]
    assert len(dependent) >= 1


# ---------------------------------------------------------------------------
# Abstract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_abstract_is_150_words_or_fewer():
    """Abstract must be 150 words or fewer per USPTO rules."""
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An advanced widget system.")
    assert result.abstract is not None
    assert len(result.abstract.split()) <= 150


# ---------------------------------------------------------------------------
# ADS data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ads_data_populated():
    """ads_data must be non-None and contain expected keys."""
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An advanced widget system.")
    assert result.ads_data is not None


@pytest.mark.asyncio
async def test_ads_data_has_filing_checklist():
    """ads_data must have a filing_checklist with all 8 required items."""
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An advanced widget system.")
    checklist = result.ads_data.get("filing_checklist", [])
    assert len(checklist) == 8


@pytest.mark.asyncio
async def test_filing_checklist_contains_required_items():
    """Filing checklist must include transmittal, fee, spec, claims, abstract, drawings, ADS, oath."""
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An advanced widget system.")
    checklist = result.ads_data.get("filing_checklist", [])
    checklist_text = " ".join(checklist).lower()
    assert "transmittal" in checklist_text
    assert "fee" in checklist_text
    assert "specification" in checklist_text
    assert "claims" in checklist_text
    assert "abstract" in checklist_text
    assert "drawings" in checklist_text
    assert "ads" in checklist_text or "application data sheet" in checklist_text
    assert "oath" in checklist_text or "declaration" in checklist_text


@pytest.mark.asyncio
async def test_ads_data_has_title():
    """ads_data must contain the invention title."""
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An advanced widget system.")
    assert result.ads_data.get("title") is not None


# ---------------------------------------------------------------------------
# 12-month deadline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nonprovisional_deadline_calculated_when_provisional_filed_at_provided():
    """nonprovisional_deadline is set to provisional_filed_at + 12 months."""
    provisional_date = "2024-01-15"
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft(
        "An advanced widget system.",
        preferences={"provisional_filed_at": provisional_date},
    )
    assert result.ads_data is not None
    deadline = result.ads_data.get("nonprovisional_deadline")
    assert deadline is not None
    # Should be approximately 1 year after the provisional filing date
    expected = date(2025, 1, 15)
    # Allow a few days of tolerance around the anniversary
    deadline_date = date.fromisoformat(str(deadline)) if isinstance(deadline, str) else deadline
    assert abs((deadline_date - expected).days) <= 3


@pytest.mark.asyncio
async def test_no_deadline_when_no_provisional_filed_at():
    """nonprovisional_deadline is absent when no provisional_filed_at preference."""
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An advanced widget system.")
    assert result.ads_data is not None
    assert "nonprovisional_deadline" not in result.ads_data


# ---------------------------------------------------------------------------
# Claim breadth preferences
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_claim_breadth_broad_included_in_prompt():
    """claim_breadth=broad preference is passed through to the LLM prompt."""
    llm = _make_llm()
    drafter = NonProvisionalDrafter(llm_provider=llm)
    await drafter.draft("An advanced widget system.", preferences={"claim_breadth": "broad"})
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "broad" in prompt


@pytest.mark.asyncio
async def test_claim_breadth_narrow_included_in_prompt():
    """claim_breadth=narrow preference is passed through to the LLM prompt."""
    llm = _make_llm()
    drafter = NonProvisionalDrafter(llm_provider=llm)
    await drafter.draft("An advanced widget system.", preferences={"claim_breadth": "narrow"})
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "narrow" in prompt


@pytest.mark.asyncio
async def test_claim_breadth_balanced_included_in_prompt():
    """claim_breadth=balanced preference is passed through to the LLM prompt."""
    llm = _make_llm()
    drafter = NonProvisionalDrafter(llm_provider=llm)
    await drafter.draft("An advanced widget system.", preferences={"claim_breadth": "balanced"})
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "balanced" in prompt


# ---------------------------------------------------------------------------
# LLM error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_error_returns_partial_result():
    """LLM failure returns a graceful partial result with error metadata."""
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    drafter = NonProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("An advanced widget system.")
    assert isinstance(result, DraftApplication)
    assert result.filing_format == FilingFormat.NONPROVISIONAL
    ads = result.ads_data or {}
    assert ads.get("error") is not None


@pytest.mark.asyncio
async def test_llm_error_result_has_checklist():
    """Even on LLM error, the filing checklist is present in ads_data."""
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=ValueError("Bad response"))
    drafter = NonProvisionalDrafter(llm_provider=llm)
    result = await drafter.draft("An advanced widget system.")
    assert result.ads_data is not None
    assert "filing_checklist" in result.ads_data


# ---------------------------------------------------------------------------
# Coverage: abstract truncation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_abstract_truncated_when_over_150_words():
    """Abstracts longer than 150 words are truncated to exactly 150 words."""
    long_words = " ".join(["word"] * 200)
    long_response = _MOCK_LLM_RESPONSE.replace(
        "ABSTRACT:\nAn advanced widget system comprising a multi-mode operation controller",
        f"ABSTRACT:\n{long_words}\nXXXSTOP",
    )
    # Build a fresh response with a very long abstract block
    long_abstract_response = (
        "TITLE: Test Invention\n\n"
        f"ABSTRACT:\n{long_words}\n\n"
        "BACKGROUND:\nSome background.\n\n"
        "SUMMARY:\nSome summary.\n\n"
        "DETAILED_DESCRIPTION:\nSome details.\n\n"
        "EMBODIMENT 1:\nTitle: First\nDescription: First embodiment.\n\n"
        "EMBODIMENT 2:\nTitle: Second\nDescription: Second embodiment.\n\n"
        "EMBODIMENT 3:\nTitle: Third\nDescription: Third embodiment.\n\n"
        "CLAIM 1 (independent):\nA device comprising a housing.\n\n"
        "CLAIM 2 (dependent on 1):\nThe device of claim 1, wherein the housing is metal.\n"
    )
    drafter = NonProvisionalDrafter(llm_provider=_make_llm(long_abstract_response))
    result = await drafter.draft("A device.")
    assert result.abstract is not None
    assert len(result.abstract.split()) <= 150


# ---------------------------------------------------------------------------
# Coverage: Feb-29 leap-year deadline fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deadline_for_feb29_provisional():
    """Deadline calculation falls back to +365 days for Feb-29 provisionals."""
    # 2024 is a leap year; 2025 has no Feb 29 — triggers ValueError fallback
    drafter = NonProvisionalDrafter(llm_provider=_make_llm())
    result = await drafter.draft(
        "An advanced widget system.",
        preferences={"provisional_filed_at": "2024-02-29"},
    )
    deadline_str = result.ads_data.get("nonprovisional_deadline")
    assert deadline_str is not None
    deadline_date = date.fromisoformat(deadline_str)
    # Should be 365 days after 2024-02-29 = 2025-02-28
    expected = date(2024, 2, 29) + timedelta(days=365)
    assert deadline_date == expected


# ---------------------------------------------------------------------------
# Coverage: prior art in prompt + unknown preference keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prior_art_included_in_nonprovisional_prompt():
    """Prior art patent ID appears in the LLM prompt for non-provisional drafting."""
    llm = _make_llm()
    drafter = NonProvisionalDrafter(llm_provider=llm)
    prior_art = [_make_search_result("US9999001", "Prior Art Reference")]
    await drafter.draft("An advanced widget system.", prior_art_results=prior_art)
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "US9999001" in prompt or "Prior Art Reference" in prompt


@pytest.mark.asyncio
async def test_unknown_preference_keys_forwarded_to_nonprovisional_prompt():
    """Unknown preference keys beyond standard ones appear in the prompt."""
    llm = _make_llm()
    drafter = NonProvisionalDrafter(llm_provider=llm)
    prefs = {
        "claim_breadth": "broad",
        "num_embodiments": 3,
        "jurisdiction": "US",
        "language": "plain",
    }
    await drafter.draft("An advanced widget system.", preferences=prefs)
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "jurisdiction" in prompt
    assert "language" in prompt
