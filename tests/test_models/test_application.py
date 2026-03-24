import pytest
from core.models.application import (
    DraftApplication, FilingFormat, Embodiment, ReviewNote,
    ReviewType, ReviewSeverity, Specification,
)
from core.models.patent import Claim


def test_filing_format_enum():
    assert FilingFormat.PROVISIONAL == "provisional"
    assert FilingFormat.NONPROVISIONAL == "nonprovisional"
    assert FilingFormat.PCT == "pct"


def test_embodiment():
    e = Embodiment(title="Cloud-based implementation", description="In this embodiment...")
    assert e.title == "Cloud-based implementation"


def test_specification():
    spec = Specification(
        background="The field of...",
        summary="The present invention...",
        detailed_description="Referring to FIG. 1...",
        embodiments=[Embodiment(title="First", description="...")],
    )
    assert len(spec.embodiments) == 1


def test_review_note():
    note = ReviewNote(
        type=ReviewType.NOVELTY_102,
        finding="Claim 1 anticipated by US11234567",
        severity=ReviewSeverity.HIGH,
        suggestion="Narrow claim to focus on adaptive frequency hopping",
    )
    assert note.severity == "high"


def test_draft_application_abstract_length():
    short_abstract = "A system for wireless power transfer."
    app = DraftApplication(
        title="TEST",
        filing_format=FilingFormat.PROVISIONAL,
        abstract=short_abstract,
        specification=Specification(
            background="", summary="", detailed_description="", embodiments=[]
        ),
        claims=[Claim(number=1, type="independent", text="A system...")],
    )
    assert app.abstract == short_abstract


def test_draft_application_abstract_too_long():
    long_abstract = " ".join(["word"] * 200)
    with pytest.raises(ValueError, match="150 words"):
        DraftApplication(
            title="TEST",
            filing_format=FilingFormat.PROVISIONAL,
            abstract=long_abstract,
            specification=Specification(
                background="", summary="", detailed_description="", embodiments=[]
            ),
            claims=[Claim(number=1, type="independent", text="A system...")],
        )
