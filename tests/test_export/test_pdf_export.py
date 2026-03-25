"""Tests for core/export/pdf_export.py."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from core.export.pdf_export import DISCLAIMER, _build_html, _esc, export_pdf
from core.models.application import DraftApplication, Embodiment, FilingFormat, Specification
from core.models.patent import Claim


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_draft(
    filing_format: FilingFormat = FilingFormat.PROVISIONAL,
    abstract: str | None = "A system for optimizing widget performance using AI.",
    with_claims: bool = True,
    with_embodiments: bool = True,
) -> DraftApplication:
    embodiments = (
        [Embodiment(title="Cloud Implementation", description="Deployed as a cloud service.")]
        if with_embodiments
        else []
    )
    claims = (
        [Claim(number=1, type="independent", text="A system comprising a processor.")]
        if with_claims
        else []
    )
    return DraftApplication(
        filing_format=filing_format,
        title="Smart Widget Optimization System",
        abstract=abstract,
        specification=Specification(
            background="Prior art lacked adaptive control.",
            summary="The present invention provides adaptive control.",
            detailed_description="The system comprises a processor and sensor array.",
            embodiments=embodiments,
        ),
        claims=claims,
    )


def _make_weasyprint_mock() -> ModuleType:
    """Return a mock weasyprint module that produces fake PDF bytes."""
    mock_wp = MagicMock()
    mock_html_instance = MagicMock()
    mock_html_instance.write_pdf.return_value = b"%PDF-1.4 fake pdf content"
    mock_wp.HTML.return_value = mock_html_instance
    return mock_wp


# ---------------------------------------------------------------------------
# _build_html unit tests (no weasyprint needed)
# ---------------------------------------------------------------------------

def test_build_html_contains_title():
    """_build_html includes the uppercased title."""
    draft = _make_draft()
    html = _build_html(draft)
    assert "SMART WIDGET OPTIMIZATION SYSTEM" in html


def test_build_html_contains_abstract():
    """_build_html includes the abstract text."""
    draft = _make_draft()
    html = _build_html(draft)
    assert "optimizing widget performance" in html


def test_build_html_contains_no_abstract_placeholder():
    """_build_html shows placeholder when abstract is None."""
    draft = _make_draft(abstract=None)
    html = _build_html(draft)
    assert "No abstract provided" in html


def test_build_html_contains_specification_sections():
    """_build_html includes all specification section headings."""
    draft = _make_draft()
    html = _build_html(draft)
    assert "BACKGROUND OF THE INVENTION" in html
    assert "SUMMARY OF THE INVENTION" in html
    assert "DETAILED DESCRIPTION OF THE INVENTION" in html


def test_build_html_contains_claims():
    """_build_html includes claim text."""
    draft = _make_draft()
    html = _build_html(draft)
    assert "A system comprising a processor." in html


def test_build_html_contains_disclaimer():
    """_build_html includes the filing disclaimer."""
    draft = _make_draft()
    html = _build_html(draft)
    assert DISCLAIMER in html


def test_build_html_escapes_special_chars():
    """_build_html escapes HTML special characters in content."""
    draft = _make_draft()
    draft = draft.model_copy(
        update={
            "specification": Specification(
                background="Test <background> & 'quotes'",
                summary="Summary",
                detailed_description="Detail",
                embodiments=[],
            )
        }
    )
    html = _build_html(draft)
    assert "&lt;background&gt;" in html
    assert "&amp;" in html


# ---------------------------------------------------------------------------
# export_pdf with mocked weasyprint
# ---------------------------------------------------------------------------

def test_export_pdf_returns_bytes():
    """export_pdf returns bytes when weasyprint is available."""
    draft = _make_draft()
    with patch.dict(sys.modules, {"weasyprint": _make_weasyprint_mock()}):
        result = export_pdf(draft)
    assert isinstance(result, bytes)


def test_export_pdf_returns_non_empty():
    """export_pdf returns non-empty bytes."""
    draft = _make_draft()
    with patch.dict(sys.modules, {"weasyprint": _make_weasyprint_mock()}):
        result = export_pdf(draft)
    assert len(result) > 0


def test_export_pdf_starts_with_pdf_magic():
    """PDF output must start with %PDF magic bytes."""
    draft = _make_draft()
    with patch.dict(sys.modules, {"weasyprint": _make_weasyprint_mock()}):
        result = export_pdf(draft)
    assert result[:4] == b"%PDF", "PDF output must start with %PDF magic bytes"


def test_export_pdf_works_with_provisional():
    """export_pdf works with PROVISIONAL filing format."""
    draft = _make_draft(filing_format=FilingFormat.PROVISIONAL)
    with patch.dict(sys.modules, {"weasyprint": _make_weasyprint_mock()}):
        result = export_pdf(draft)
    assert result[:4] == b"%PDF"


def test_export_pdf_works_with_nonprovisional():
    """export_pdf works with NONPROVISIONAL filing format."""
    draft = _make_draft(filing_format=FilingFormat.NONPROVISIONAL)
    with patch.dict(sys.modules, {"weasyprint": _make_weasyprint_mock()}):
        result = export_pdf(draft)
    assert result[:4] == b"%PDF"


def test_export_pdf_works_with_pct():
    """export_pdf works with PCT filing format."""
    draft = _make_draft(filing_format=FilingFormat.PCT)
    with patch.dict(sys.modules, {"weasyprint": _make_weasyprint_mock()}):
        result = export_pdf(draft)
    assert result[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# Graceful weasyprint import failure
# ---------------------------------------------------------------------------

def test_export_pdf_raises_import_error_when_weasyprint_unavailable():
    """export_pdf raises ImportError when weasyprint system deps are missing."""
    draft = _make_draft()

    # Remove weasyprint from sys.modules so the import inside export_pdf triggers
    with patch.dict(sys.modules, {"weasyprint": None}):
        with pytest.raises(ImportError, match="WeasyPrint system dependencies"):
            export_pdf(draft)


def test_export_pdf_raises_import_error_on_os_error():
    """export_pdf raises ImportError when weasyprint raises OSError on import."""
    draft = _make_draft()

    class _BrokenModule:
        """Simulates a partially-imported module that raises OSError on attribute access."""
        def __getattr__(self, name):
            raise OSError("cannot load library 'libgobject-2.0-0'")

    # Patch the import so weasyprint is present but broken
    original = sys.modules.get("weasyprint")
    try:
        sys.modules.pop("weasyprint", None)
        # We patch builtins.__import__ to raise OSError for weasyprint
        real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def _raising_import(name, *args, **kwargs):
            if name == "weasyprint":
                raise OSError("cannot load library 'libgobject-2.0-0'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_raising_import):
            with pytest.raises((ImportError, OSError)):
                export_pdf(draft)
    finally:
        if original is not None:
            sys.modules["weasyprint"] = original
        else:
            sys.modules.pop("weasyprint", None)


def test_build_html_contains_drawings_description():
    """_build_html includes drawings description section when present."""
    draft = _make_draft()
    draft = draft.model_copy(update={"drawings_description": "FIG. 1 shows the main architecture."})
    html = _build_html(draft)
    assert "BRIEF DESCRIPTION OF THE DRAWINGS" in html
    assert "FIG. 1 shows the main architecture." in html


def test_build_html_esc_handles_none():
    """_esc returns empty string for None input."""
    assert _esc(None) == ""


def test_build_html_esc_escapes_characters():
    """_esc correctly escapes HTML special characters."""
    assert _esc("a & b") == "a &amp; b"
    assert _esc("<tag>") == "&lt;tag&gt;"
    assert _esc('"quoted"') == "&quot;quoted&quot;"


def test_build_html_no_drawings_section_when_absent():
    """_build_html omits drawings section when drawings_description is None."""
    draft = _make_draft()
    draft = draft.model_copy(update={"drawings_description": None})
    html = _build_html(draft)
    assert "BRIEF DESCRIPTION OF THE DRAWINGS" not in html
