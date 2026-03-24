import pytest
from datetime import date
from core.models.patent import (
    Inventor, Assignee, Citation, Claim, SearchResult, Patent,
    SearchStrategy, PatentType,
)


def test_inventor_creation():
    inv = Inventor(first="John", last="Smith")
    assert inv.first == "John"
    assert inv.last == "Smith"
    assert inv.full_name == "John Smith"


def test_assignee_creation():
    a = Assignee(organization="Google LLC")
    assert a.organization == "Google LLC"
    a2 = Assignee(first="Jane", last="Doe")
    assert a2.organization is None


def test_claim_independent():
    c = Claim(number=1, type="independent", text="A system comprising...")
    assert c.number == 1
    assert c.depends_on is None


def test_claim_dependent():
    c = Claim(number=2, type="dependent", depends_on=1, text="The system of claim 1, wherein...")
    assert c.depends_on == 1


def test_claim_dependent_requires_depends_on():
    with pytest.raises(ValueError):
        Claim(number=2, type="dependent", text="Missing depends_on")


def test_search_result_creation():
    sr = SearchResult(
        patent_id="US11234567",
        title="WIRELESS POWER SYSTEM",
        provider="patentsview",
        strategy=SearchStrategy.KEYWORD,
    )
    assert sr.patent_id == "US11234567"
    assert sr.relevance_score is None


def test_search_result_with_full_data():
    sr = SearchResult(
        patent_id="US11234567",
        title="WIRELESS POWER SYSTEM",
        abstract="A system for wirelessly...",
        patent_date=date(2023, 5, 15),
        inventors=[Inventor(first="John", last="Smith")],
        assignees=[Assignee(organization="MedTech Inc")],
        cpc_codes=["A61N1/372"],
        relevance_score=0.85,
        relevance_notes="Strong overlap in power transfer method",
        provider="patentsview",
        strategy=SearchStrategy.KEYWORD,
    )
    assert sr.inventors[0].full_name == "John Smith"
    assert sr.relevance_score == 0.85
    assert len(sr.cpc_codes) == 1


def test_patent_type_enum():
    assert PatentType.UTILITY == "utility"
    assert PatentType.DESIGN == "design"


def test_search_strategy_enum():
    assert SearchStrategy.KEYWORD == "keyword"
    assert SearchStrategy.CLASSIFICATION == "classification"
    assert SearchStrategy.CITATION == "citation"
    assert SearchStrategy.ASSIGNEE == "assignee"
