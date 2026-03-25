"""PDF export for patent draft applications via WeasyPrint."""
from __future__ import annotations

import structlog

from core.models.application import DraftApplication

logger = structlog.get_logger(__name__)

DISCLAIMER = (
    "This document was generated with AI assistance. "
    "Review by a qualified patent attorney is recommended before filing."
)

_CSS = """
@page {
    size: letter;
    margin: 1in 0.75in 1in 0.75in;
}

body {
    font-family: "Times New Roman", Times, serif;
    font-size: 12pt;
    line-height: 2;
    color: #000000;
}

h1, h2, h3 {
    font-family: "Times New Roman", Times, serif;
    font-size: 12pt;
    font-weight: bold;
    margin-top: 1em;
    margin-bottom: 0.5em;
}

p {
    margin: 0 0 1em 0;
    text-align: justify;
}

.page-break {
    page-break-before: always;
}

.title {
    text-align: center;
    font-weight: bold;
    text-transform: uppercase;
    margin-bottom: 0.5em;
}

.filing-format {
    text-align: center;
    margin-bottom: 2em;
}

.claim {
    margin-bottom: 0.5em;
}

.disclaimer {
    text-align: center;
    font-style: italic;
    margin-top: 2em;
    font-size: 10pt;
}
"""


def _esc(text: str | None) -> str:
    """Escape HTML special characters; return empty string for None."""
    if text is None:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _build_html(draft: DraftApplication) -> str:
    """Build an HTML string from a DraftApplication."""
    esc = _esc

    lines: list[str] = []
    lines.append("<!DOCTYPE html>")
    lines.append("<html><head>")
    lines.append('<meta charset="utf-8">')
    lines.append(f"<title>{esc(draft.title)}</title>")
    lines.append(f"<style>{_CSS}</style>")
    lines.append("</head><body>")

    # Title page
    lines.append(f'<p class="title">{esc(draft.title.upper())}</p>')
    lines.append(f'<p class="filing-format">Filing Format: {esc(draft.filing_format.upper())}</p>')

    # Abstract
    lines.append('<div class="page-break">')
    lines.append("<h1>ABSTRACT</h1>")
    if draft.abstract:
        lines.append(f"<p>{esc(draft.abstract)}</p>")
    else:
        lines.append("<p>(No abstract provided.)</p>")
    lines.append("</div>")

    # Specification
    lines.append('<div class="page-break">')
    lines.append("<h1>SPECIFICATION</h1>")

    lines.append("<h2>BACKGROUND OF THE INVENTION</h2>")
    lines.append(f"<p>{esc(draft.specification.background)}</p>")

    lines.append("<h2>SUMMARY OF THE INVENTION</h2>")
    lines.append(f"<p>{esc(draft.specification.summary)}</p>")

    lines.append("<h2>DETAILED DESCRIPTION OF THE INVENTION</h2>")
    lines.append(f"<p>{esc(draft.specification.detailed_description)}</p>")

    for idx, embodiment in enumerate(draft.specification.embodiments, start=1):
        lines.append(f"<h3>Embodiment {idx}: {esc(embodiment.title)}</h3>")
        lines.append(f"<p>{esc(embodiment.description)}</p>")

    if draft.drawings_description:
        lines.append("<h2>BRIEF DESCRIPTION OF THE DRAWINGS</h2>")
        lines.append(f"<p>{esc(draft.drawings_description)}</p>")

    lines.append("</div>")

    # Claims
    lines.append('<div class="page-break">')
    lines.append("<h1>CLAIMS</h1>")
    for claim in draft.claims:
        lines.append(f'<p class="claim">{claim.number}. {esc(claim.text)}</p>')
    lines.append("</div>")

    # Disclaimer
    lines.append(f'<p class="disclaimer">{esc(DISCLAIMER)}</p>')

    lines.append("</body></html>")
    return "\n".join(lines)


def export_pdf(draft: DraftApplication) -> bytes:
    """Export a DraftApplication to a USPTO-formatted PDF file.

    Returns the document as raw bytes.

    If WeasyPrint system dependencies (pango, cairo) are not available,
    logs a warning and raises ImportError so callers can handle gracefully.
    """
    log = logger.bind(draft_id=str(draft.id), filing_format=draft.filing_format)
    log.info("starting_pdf_export")

    try:
        import weasyprint  # noqa: PLC0415
    except (ImportError, OSError) as exc:
        log.warning(
            "weasyprint_unavailable",
            reason=str(exc),
            hint="Install system dependencies: pango, cairo, gdk-pixbuf2",
        )
        raise ImportError(
            "WeasyPrint system dependencies are not available. "
            "Install pango, cairo, and gdk-pixbuf2 before using PDF export."
        ) from exc

    html_content = _build_html(draft)
    pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()

    log.info("pdf_export_complete", size_bytes=len(pdf_bytes))
    return pdf_bytes
