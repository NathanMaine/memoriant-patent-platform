"""Tests for core/drafting/pct.py — PCTDrafter."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.llm.base import LLMProvider, LLMResponse
from core.models.application import DraftApplication, FilingFormat
from core.drafting.pct import PCTDrafter


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_MOCK_LLM_RESPONSE = """\
TITLE: International Widget System with Global Compatibility

ABSTRACT:
An international widget system providing global compatibility across
regulatory jurisdictions. The system comprises a core processing unit,
a universal interface module, and a compliance layer that adapts system
behavior to regional requirements. The invention enables single-product
deployment across multiple international markets without hardware
modification, reducing development costs and time-to-market.

BACKGROUND:
International product deployment has historically required separate
product variants for each target jurisdiction due to incompatible
regulatory requirements and technical standards.

SUMMARY:
The present invention provides an international widget system with
a software-configurable compliance layer that adapts to jurisdictional
requirements without hardware changes.

DETAILED_DESCRIPTION:
The international widget system comprises a core processing unit coupled
to a universal interface module and a compliance layer. The compliance
layer stores jurisdiction profiles indexed by region code. On startup,
the system detects the operating jurisdiction and loads the corresponding
profile to configure operational parameters.

EMBODIMENT 1:
Title: European Market Configuration
Description: In a first embodiment, the system is configured for European
Union markets, applying CE marking requirements and ETSI standards to
the universal interface module.

EMBODIMENT 2:
Title: North American Market Configuration
Description: In a second embodiment, the system applies FCC Part 15
requirements and UL safety standards appropriate for the North American
market.

EMBODIMENT 3:
Title: Asia-Pacific Market Configuration
Description: In a third embodiment, the system supports Asia-Pacific
regional standards including Japanese TELEC and Korean KCC certifications.

CLAIM 1 (independent):
An international widget system comprising: a core processing unit; a
universal interface module operatively connected to the core processing
unit; and a compliance layer configured to store a plurality of
jurisdiction profiles and to apply a selected jurisdiction profile
to configure operational parameters of the system.

CLAIM 2 (dependent on 1):
The international widget system of claim 1, wherein the compliance layer
is configured to automatically detect an operating jurisdiction and
select a corresponding jurisdiction profile.

CLAIM 3 (dependent on 1):
The international widget system of claim 1, wherein each jurisdiction
profile defines radio frequency parameters compliant with the regulations
of a corresponding jurisdiction.
"""


def _make_llm(response_text: str = _MOCK_LLM_RESPONSE) -> LLMProvider:
    provider = MagicMock(spec=LLMProvider)
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            content=response_text,
            model="mock-model",
            tokens_used=700,
        )
    )
    return provider


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_pct_drafter_instantiation():
    """PCTDrafter can be constructed with an LLMProvider."""
    llm = _make_llm()
    drafter = PCTDrafter(llm_provider=llm)
    assert drafter is not None
    assert drafter.llm_provider is llm


# ---------------------------------------------------------------------------
# Filing format
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_draft_application_type():
    """draft() returns a DraftApplication instance."""
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.")
    assert isinstance(result, DraftApplication)


@pytest.mark.asyncio
async def test_filing_format_is_pct():
    """Returned DraftApplication has filing_format == 'pct'."""
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.")
    assert result.filing_format == FilingFormat.PCT


# ---------------------------------------------------------------------------
# Filing checklist — PCT-specific items
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pct_filing_checklist_present():
    """ads_data must contain a filing_checklist."""
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.")
    assert result.ads_data is not None
    assert "filing_checklist" in result.ads_data


@pytest.mark.asyncio
async def test_pct_filing_checklist_has_pct_request_form():
    """Filing checklist must include the PCT request form (PCT/RO/101)."""
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.")
    checklist = result.ads_data.get("filing_checklist", [])
    checklist_text = " ".join(checklist).lower()
    assert "pct/ro/101" in checklist_text or "pct request" in checklist_text


@pytest.mark.asyncio
async def test_pct_filing_checklist_has_designation_of_states():
    """Filing checklist must include designation of states."""
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.")
    checklist = result.ads_data.get("filing_checklist", [])
    checklist_text = " ".join(checklist).lower()
    assert "designation" in checklist_text or "states" in checklist_text


@pytest.mark.asyncio
async def test_pct_filing_checklist_has_priority_document():
    """Filing checklist must include priority document."""
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.")
    checklist = result.ads_data.get("filing_checklist", [])
    checklist_text = " ".join(checklist).lower()
    assert "priority" in checklist_text


@pytest.mark.asyncio
async def test_pct_filing_checklist_has_all_required_items():
    """PCT filing checklist must have at least 8 items."""
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.")
    checklist = result.ads_data.get("filing_checklist", [])
    assert len(checklist) >= 8


# ---------------------------------------------------------------------------
# A4 paper format note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a4_paper_note_present_in_specification_metadata():
    """Specification or ads_data must note A4 paper format requirement."""
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.")
    # A4 note can be in ads_data or specification fields
    ads_text = str(result.ads_data or "").lower()
    spec_text = (
        result.specification.background
        + result.specification.summary
        + result.specification.detailed_description
    ).lower()
    assert "a4" in ads_text or "a4" in spec_text


# ---------------------------------------------------------------------------
# Specification and claims
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pct_draft_has_specification():
    """Draft must have a non-empty specification."""
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.")
    assert result.specification is not None
    assert result.specification.detailed_description


@pytest.mark.asyncio
async def test_pct_draft_has_claims():
    """Draft must include at least one claim."""
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.")
    assert len(result.claims) >= 1


@pytest.mark.asyncio
async def test_pct_draft_has_abstract():
    """PCT application must include an abstract."""
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.")
    assert result.abstract is not None
    assert len(result.abstract.strip()) > 0


# ---------------------------------------------------------------------------
# LLM error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_error_returns_partial_result():
    """LLM failure returns a graceful partial result with error metadata."""
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    drafter = PCTDrafter(llm_provider=llm)
    result = await drafter.draft("An international widget system.")
    assert isinstance(result, DraftApplication)
    assert result.filing_format == FilingFormat.PCT
    ads = result.ads_data or {}
    assert ads.get("error") is not None


@pytest.mark.asyncio
async def test_llm_error_result_has_pct_checklist():
    """Even on LLM error, the PCT filing checklist is present in ads_data."""
    llm = MagicMock(spec=LLMProvider)
    llm.generate = AsyncMock(side_effect=ConnectionError("Network failure"))
    drafter = PCTDrafter(llm_provider=llm)
    result = await drafter.draft("An international widget system.")
    assert result.ads_data is not None
    checklist = result.ads_data.get("filing_checklist", [])
    checklist_text = " ".join(checklist).lower()
    assert "pct" in checklist_text or "pct/ro/101" in checklist_text


# ---------------------------------------------------------------------------
# Coverage: abstract truncation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_abstract_truncated_when_over_150_words():
    """Abstracts longer than 150 words are truncated to 150 words in PCT drafts."""
    long_words = " ".join(["global"] * 200)
    long_abstract_response = (
        "TITLE: PCT Test Invention\n\n"
        f"ABSTRACT:\n{long_words}\n\n"
        "BACKGROUND:\nPrior art lacked international compatibility.\n\n"
        "SUMMARY:\nThis invention provides global compatibility.\n\n"
        "DETAILED_DESCRIPTION:\nThe system comprises a core unit.\n\n"
        "EMBODIMENT 1:\nTitle: EU Config\nDescription: European configuration.\n\n"
        "CLAIM 1 (independent):\nA system comprising a core processing unit.\n\n"
        "CLAIM 2 (dependent on 1):\nThe system of claim 1 with a compliance layer.\n"
    )
    drafter = PCTDrafter(llm_provider=_make_llm(long_abstract_response))
    result = await drafter.draft("A global system.")
    assert result.abstract is not None
    assert len(result.abstract.split()) <= 150


# ---------------------------------------------------------------------------
# Coverage: priority_application preference and prior art in prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_priority_application_preference_stored_in_ads_data():
    """priority_application preference is stored in ads_data."""
    prefs = {"priority_application": "US18/123456"}
    drafter = PCTDrafter(llm_provider=_make_llm())
    result = await drafter.draft("An international widget system.", preferences=prefs)
    assert result.ads_data.get("priority_application") == "US18/123456"


@pytest.mark.asyncio
async def test_prior_art_included_in_pct_prompt():
    """Prior art patent ID appears in the LLM prompt for PCT drafting."""
    from core.models.patent import SearchResult, SearchStrategy
    llm = _make_llm()
    drafter = PCTDrafter(llm_provider=llm)
    prior_art = [
        SearchResult(
            patent_id="EP3456789",
            title="European Prior Widget",
            abstract="A prior widget.",
            provider="mock",
            strategy=SearchStrategy.KEYWORD,
        )
    ]
    await drafter.draft("An international widget system.", prior_art_results=prior_art)
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "EP3456789" in prompt or "European Prior Widget" in prompt


@pytest.mark.asyncio
async def test_num_embodiments_preference_in_pct_prompt():
    """num_embodiments preference is included in the PCT prompt."""
    llm = _make_llm()
    drafter = PCTDrafter(llm_provider=llm)
    await drafter.draft("An international widget system.", preferences={"num_embodiments": 4})
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "4" in prompt


@pytest.mark.asyncio
async def test_unknown_preference_keys_forwarded_to_pct_prompt():
    """Unknown preference keys beyond standard ones appear in the PCT prompt."""
    llm = _make_llm()
    drafter = PCTDrafter(llm_provider=llm)
    prefs = {
        "claim_breadth": "broad",
        "num_embodiments": 3,
        "target_jurisdictions": "EP,JP,CN",
    }
    await drafter.draft("An international widget system.", preferences=prefs)
    call_args = llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
    assert "target_jurisdictions" in prompt
