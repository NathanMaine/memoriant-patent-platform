"""Shared pytest fixtures available to all test modules.

Import by declaring the fixture name as a function parameter — no explicit
import required (pytest discovers these from conftest.py automatically).
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.llm.base import LLMProvider, LLMResponse
from core.models.patent import Inventor, Assignee, SearchResult, SearchStrategy
from core.models.application import (
    DraftApplication,
    FilingFormat,
    Specification,
    Claim,
)


# ---------------------------------------------------------------------------
# LLM fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm():
    """Shared mock LLM provider that returns structured patent text."""
    llm = AsyncMock(spec=LLMProvider)
    llm.generate = AsyncMock(
        return_value=LLMResponse(
            content=(
                "TITLE: Test Patent\n"
                "ABSTRACT: A test invention.\n"
                "BACKGROUND: Background text.\n"
                "SUMMARY: Summary text.\n"
                "DETAILED DESCRIPTION: Description.\n"
                "EMBODIMENT 1: First embodiment.\n"
                "CLAIM 1: A system comprising a test."
            ),
            tokens_used=100,
            model="test-model",
        )
    )
    llm.generate_with_thinking = AsyncMock(
        return_value=LLMResponse(
            content="Extended thinking output.",
            tokens_used=500,
            model="test-model",
            thinking="<thinking>I considered the problem thoroughly.</thinking>",
        )
    )
    return llm


# ---------------------------------------------------------------------------
# Patent model fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_search_result():
    """Shared sample SearchResult for testing."""
    return SearchResult(
        patent_id="US12345678",
        title="TEST WIRELESS POWER SYSTEM",
        abstract="A system for wireless power transfer.",
        inventors=[Inventor(first="John", last="Smith")],
        assignees=[Assignee(organization="TestCorp")],
        cpc_codes=["H02J50/10"],
        provider="patentsview",
        strategy=SearchStrategy.KEYWORD,
    )


@pytest.fixture
def sample_search_results(sample_search_result):
    """A small list of SearchResult objects for multi-result tests."""
    second = SearchResult(
        patent_id="US87654321",
        title="ADVANCED ENERGY HARVESTING DEVICE",
        abstract="Harvests ambient RF energy.",
        inventors=[Inventor(first="Ada", last="Lovelace")],
        assignees=[Assignee(organization="EnergyTech LLC")],
        cpc_codes=["H02J7/34"],
        relevance_score=0.72,
        provider="patentsview",
        strategy=SearchStrategy.KEYWORD,
    )
    return [sample_search_result, second]


# ---------------------------------------------------------------------------
# Application fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_specification():
    """Minimal valid Specification for testing."""
    return Specification(
        background="Existing solutions lack efficiency in wireless power transfer.",
        summary="A system and method for high-efficiency wireless power transfer.",
        detailed_description=(
            "The invention comprises a transmitter coil and a receiver coil "
            "arranged for resonant inductive coupling at a frequency of 6.78 MHz."
        ),
    )


@pytest.fixture
def sample_draft(sample_specification):
    """Shared sample DraftApplication for testing."""
    return DraftApplication(
        filing_format=FilingFormat.PROVISIONAL,
        title="HIGH-EFFICIENCY WIRELESS POWER TRANSFER SYSTEM",
        abstract="A wireless power transfer system using resonant inductive coupling.",
        specification=sample_specification,
        claims=[
            Claim(number=1, type="independent", text="A wireless charging system comprising a transmitter coil."),
            Claim(number=2, type="dependent", depends_on=1, text="The system of claim 1, wherein the transmitter coil operates at 6.78 MHz."),
        ],
    )
