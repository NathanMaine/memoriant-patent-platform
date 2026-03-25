"""Non-provisional (utility) patent application drafter.

Generates a USPTO non-provisional utility application (35 USC 111(a)) from an
invention description and optional prior art context.  The output includes a
formal specification, independent and dependent claims, an abstract (<=150
words, separate page), drawing descriptions, and an Application Data Sheet
(ADS).

The drafter tracks the 12-month deadline from a previously-filed provisional
application when ``preferences["provisional_filed_at"]`` is supplied.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import structlog

from core.drafting.base import Drafter
from core.llm.base import LLMProvider
from core.models.application import (
    DraftApplication,
    Embodiment,
    FilingFormat,
    Specification,
)
from core.models.patent import Claim, SearchResult

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert patent attorney specialising in USPTO non-provisional "
    "utility patent applications under 35 USC 111(a).\n\n"
    "KEY RULES FOR NON-PROVISIONAL APPLICATIONS:\n"
    "1. A formal specification is required, with background, summary, and "
    "detailed description sections that enable a person skilled in the art to "
    "make and use the invention.\n"
    "2. Claims are REQUIRED.  Draft layered claims: at least one broad "
    "independent claim followed by narrower dependent fallback claims.\n"
    "3. An abstract of 150 words or fewer must appear on a separate page.\n"
    "4. Description of drawings is required if drawings are included.\n"
    "5. An Application Data Sheet (ADS) must identify inventors, title, and "
    "correspondence address.  If a provisional was previously filed, the ADS "
    "must include domestic priority information.\n\n"
    "OUTPUT FORMAT — reply in EXACTLY this structure (use the exact headings):\n"
    "TITLE: <invention title>\n\n"
    "ABSTRACT:\n<<=150-word abstract, suitable for a separate page>\n\n"
    "BACKGROUND:\n<background of the invention, problems in the prior art>\n\n"
    "SUMMARY:\n<summary of the invention>\n\n"
    "DETAILED_DESCRIPTION:\n<enabling detailed description>\n\n"
    "EMBODIMENT 1:\n"
    "Title: <short title>\n"
    "Description: <description of this embodiment>\n\n"
    "(Add EMBODIMENT 2:, EMBODIMENT 3:, etc. as needed — aim for at least 3.)\n\n"
    "CLAIM 1 (independent):\n<broad independent claim text>\n\n"
    "CLAIM 2 (dependent on 1):\n<narrower dependent claim text>\n\n"
    "(Add further claims as needed.)\n\n"
    "Do not include any text outside this structure."
)

# ---------------------------------------------------------------------------
# Filing checklist — all 8 required items per USPTO rules
# ---------------------------------------------------------------------------

_FILING_CHECKLIST = [
    "Transmittal form (PTO/SB/21)",
    "Filing fee",
    "Specification",
    "Claims",
    "Abstract (separate page, ≤150 words)",
    "Drawings (if applicable)",
    "Application Data Sheet (ADS)",
    "Inventor oath/declaration",
]


# ---------------------------------------------------------------------------
# Parser helpers (shared with ProvisionalDrafter logic)
# ---------------------------------------------------------------------------

def _extract_section(text: str, header: str, next_headers: list[str]) -> str:
    """Extract text between *header* and the next recognised section heading."""
    pattern = rf"(?:^|\n){re.escape(header)}[:\s]*\n(.*?)(?=\n(?:{'|'.join(re.escape(h) for h in next_headers)})[:\s]|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_title(text: str) -> str:
    match = re.search(r"^TITLE\s*:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else "Untitled Invention"


def _extract_abstract(text: str) -> str:
    """Extract and truncate abstract to <=150 words."""
    raw = _extract_section(
        text,
        "ABSTRACT",
        ["BACKGROUND", "SUMMARY", "DETAILED_DESCRIPTION", "EMBODIMENT 1", "CLAIM 1"],
    )
    words = raw.split()
    if len(words) > 150:
        raw = " ".join(words[:150])
    return raw


def _extract_embodiments(text: str) -> list[Embodiment]:
    """Extract all EMBODIMENT N blocks."""
    embodiments: list[Embodiment] = []
    pattern = re.compile(
        r"EMBODIMENT\s+\d+\s*:\s*\n"
        r"Title\s*:\s*(.+?)\n"
        r"Description\s*:\s*(.*?)(?=\nEMBODIMENT\s+\d+|\nCLAIM\s+\d+|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        title = match.group(1).strip()
        description = match.group(2).strip()
        if title or description:
            embodiments.append(Embodiment(title=title, description=description))
    return embodiments


def _extract_claims(text: str) -> list[Claim]:
    """Extract CLAIM N blocks into Claim objects."""
    claims: list[Claim] = []
    pattern = re.compile(
        r"CLAIM\s+(\d+)\s*\(([^)]+)\)\s*:\s*\n(.*?)(?=\nCLAIM\s+\d+|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        number = int(match.group(1))
        type_raw = match.group(2).strip().lower()
        claim_text = match.group(3).strip()

        if "independent" in type_raw:
            claim_type = "independent"
            depends_on = None
        else:
            claim_type = "dependent"
            dep_match = re.search(r"on\s+(?:claim\s+)?(\d+)", type_raw, re.IGNORECASE)
            depends_on = int(dep_match.group(1)) if dep_match else 1

        if claim_text:
            claims.append(
                Claim(
                    number=number,
                    type=claim_type,
                    text=claim_text,
                    depends_on=depends_on,
                )
            )
    return claims


def _parse_llm_response(content: str) -> dict:
    """Parse the structured LLM response into component parts."""
    title = _extract_title(content)
    abstract = _extract_abstract(content)
    background = _extract_section(
        content,
        "BACKGROUND",
        ["SUMMARY", "DETAILED_DESCRIPTION", "EMBODIMENT 1", "CLAIM 1"],
    )
    summary = _extract_section(
        content,
        "SUMMARY",
        ["DETAILED_DESCRIPTION", "EMBODIMENT 1", "CLAIM 1"],
    )
    detailed_description = _extract_section(
        content,
        "DETAILED_DESCRIPTION",
        ["EMBODIMENT 1", "EMBODIMENT 2", "CLAIM 1"],
    )
    embodiments = _extract_embodiments(content)
    claims = _extract_claims(content)

    return {
        "title": title,
        "abstract": abstract,
        "background": background,
        "summary": summary,
        "detailed_description": detailed_description,
        "embodiments": embodiments,
        "claims": claims,
    }


def _calculate_nonprovisional_deadline(provisional_filed_at: str) -> date:
    """Return the 12-month non-provisional deadline from the provisional filing date.

    Uses a simple 365-day offset to approximate the anniversary.  For dates
    that would fall on a weekend or federal holiday the USPTO automatically
    extends the deadline to the next business day, but that extension is not
    modelled here.
    """
    filed = date.fromisoformat(provisional_filed_at)
    # Try same calendar date one year later; fall back to +365 days if invalid.
    try:
        deadline = filed.replace(year=filed.year + 1)
    except ValueError:
        # Handles Feb 29 in non-leap years
        deadline = filed + timedelta(days=365)
    return deadline


# ---------------------------------------------------------------------------
# NonProvisionalDrafter
# ---------------------------------------------------------------------------

class NonProvisionalDrafter(Drafter):
    """Drafts a USPTO non-provisional utility patent application.

    Sends the invention description and optional prior art context to the LLM
    and parses the structured response into a DraftApplication with
    filing_format=FilingFormat.NONPROVISIONAL.

    Key features over the provisional drafter:
    - Requires formal claims (independent + dependent layers).
    - Generates a minimum of 3 embodiments (configurable via preferences).
    - Populates ads_data with inventor names, title, correspondence address,
      and domestic priority information.
    - Computes a 12-month non-provisional deadline when
      ``preferences["provisional_filed_at"]`` is provided.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        super().__init__(llm_provider)

    async def draft(
        self,
        invention_description: str,
        prior_art_results: list[SearchResult] | None = None,
        preferences: dict | None = None,
    ) -> DraftApplication:
        """Generate a non-provisional patent application draft.

        Args:
            invention_description: Free-text description of the invention.
            prior_art_results: Optional prior art to differentiate from.
            preferences: Optional dict; recognised keys are:
                - ``claim_breadth``: "broad" | "balanced" | "narrow"
                - ``num_embodiments``: int (default 3)
                - ``provisional_filed_at``: ISO date string (YYYY-MM-DD) of
                  the previously-filed provisional application.  When present,
                  ``nonprovisional_deadline`` is added to ads_data.

        Returns:
            DraftApplication with filing_format=NONPROVISIONAL.
        """
        prefs = preferences or {}
        log = logger.bind(
            drafter="nonprovisional",
            has_prior_art=bool(prior_art_results),
            has_preferences=bool(prefs),
        )
        log.info("nonprovisional.draft.start")

        prompt = self._build_prompt(
            invention_description=invention_description,
            prior_art_results=prior_art_results,
            preferences=prefs,
        )

        try:
            response = await self.llm_provider.generate(
                prompt,
                system=_SYSTEM_PROMPT,
                max_tokens=6144,
            )
            log.info(
                "nonprovisional.draft.llm_complete",
                tokens_used=response.tokens_used,
            )

            parsed = _parse_llm_response(response.content)

            spec = Specification(
                background=parsed["background"] or "See detailed description.",
                summary=parsed["summary"] or "See detailed description.",
                detailed_description=parsed["detailed_description"] or "See detailed description.",
                embodiments=parsed["embodiments"],
            )

            ads_data = self._build_ads_data(title=parsed["title"], prefs=prefs)

            draft = DraftApplication(
                filing_format=FilingFormat.NONPROVISIONAL,
                title=parsed["title"],
                abstract=parsed["abstract"] or None,
                specification=spec,
                claims=parsed["claims"],
                ads_data=ads_data,
            )

            log.info(
                "nonprovisional.draft.complete",
                title=draft.title,
                num_claims=len(draft.claims),
                num_embodiments=len(spec.embodiments),
            )
            return draft

        except Exception as exc:  # noqa: BLE001
            log.error("nonprovisional.draft.error", error=str(exc))

            spec = Specification(
                background="Draft generation failed. See error details.",
                summary="Draft generation failed. See error details.",
                detailed_description="Draft generation failed. See error details.",
                embodiments=[],
            )
            return DraftApplication(
                filing_format=FilingFormat.NONPROVISIONAL,
                title="Draft Generation Failed",
                abstract=None,
                specification=spec,
                claims=[],
                ads_data={
                    "filing_checklist": _FILING_CHECKLIST,
                    "error": str(exc),
                },
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        invention_description: str,
        prior_art_results: list[SearchResult] | None,
        preferences: dict,
    ) -> str:
        """Assemble the user-turn prompt for the LLM."""
        num_embodiments = preferences.get("num_embodiments", 3)
        parts: list[str] = []

        parts.append("INVENTION DESCRIPTION:")
        parts.append(invention_description.strip())

        prior_art_context = self._build_prior_art_context(prior_art_results)
        if prior_art_context:
            parts.append("")
            parts.append(prior_art_context)

        parts.append("")
        parts.append("DRAFTING PREFERENCES:")
        parts.append(f"- Number of embodiments: {num_embodiments} (minimum)")
        if "claim_breadth" in preferences:
            parts.append(f"- Claim breadth: {preferences['claim_breadth']}")
        for key, value in preferences.items():
            if key not in ("claim_breadth", "num_embodiments", "provisional_filed_at"):
                parts.append(f"- {key}: {value}")

        parts.append("")
        parts.append(
            "Please draft a complete non-provisional utility patent application "
            "following the format specified in the system prompt.  Include at "
            "least one broad independent claim and multiple narrower dependent "
            "fallback claims."
        )

        return "\n".join(parts)

    def _build_ads_data(self, title: str, prefs: dict) -> dict:
        """Build the Application Data Sheet dict.

        Populates inventor_names, title, correspondence_address, and
        domestic_priority (if provisional_filed_at is in prefs).  Also
        computes nonprovisional_deadline when applicable.
        """
        ads: dict = {
            "title": title,
            "inventor_names": [],
            "correspondence_address": "",
            "filing_checklist": _FILING_CHECKLIST,
        }

        provisional_filed_at = prefs.get("provisional_filed_at")
        if provisional_filed_at:
            ads["domestic_priority"] = provisional_filed_at
            deadline = _calculate_nonprovisional_deadline(provisional_filed_at)
            ads["nonprovisional_deadline"] = deadline.isoformat()
            log = logger.bind(
                provisional_filed_at=provisional_filed_at,
                nonprovisional_deadline=ads["nonprovisional_deadline"],
            )
            log.info("nonprovisional.draft.deadline_calculated")

        return ads
