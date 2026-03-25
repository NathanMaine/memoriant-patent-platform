"""PCT (Patent Cooperation Treaty) international patent application drafter.

Generates an international patent application under the PCT (Patent Cooperation
Treaty) from an invention description and optional prior art context.  The
output follows the international application format with designation of states,
priority claim from a US filing, and A4 paper format requirements.
"""
from __future__ import annotations

import re

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
    "You are an expert patent attorney specialising in PCT (Patent Cooperation "
    "Treaty) international patent applications.\n\n"
    "KEY RULES FOR PCT APPLICATIONS:\n"
    "1. The international application must follow the PCT format prescribed by "
    "the Receiving Office (PCT/RO/101 request form).\n"
    "2. All designated states must be listed in the PCT request form.\n"
    "3. A priority claim from a US provisional or non-provisional filing should "
    "be included where applicable, citing the US application number and filing "
    "date.\n"
    "4. The specification, claims, abstract, and drawings must be prepared on "
    "A4 paper (210mm × 297mm) with margins of at least 2cm.\n"
    "5. Claims must be drafted to maximise international scope while remaining "
    "novel and non-obvious over cited prior art.\n"
    "6. The abstract must be 150 words or fewer.\n\n"
    "OUTPUT FORMAT — reply in EXACTLY this structure (use the exact headings):\n"
    "TITLE: <invention title>\n\n"
    "ABSTRACT:\n<<=150-word abstract>\n\n"
    "BACKGROUND:\n<background of the invention>\n\n"
    "SUMMARY:\n<summary of the invention>\n\n"
    "DETAILED_DESCRIPTION:\n<enabling detailed description, A4 format>\n\n"
    "EMBODIMENT 1:\n"
    "Title: <short title>\n"
    "Description: <description of this embodiment>\n\n"
    "(Add EMBODIMENT 2:, EMBODIMENT 3:, etc. as needed.)\n\n"
    "CLAIM 1 (independent):\n<broad independent claim with international scope>\n\n"
    "CLAIM 2 (dependent on 1):\n<narrower dependent claim>\n\n"
    "(Add further claims as needed.)\n\n"
    "Do not include any text outside this structure."
)

# ---------------------------------------------------------------------------
# Filing checklist — PCT-specific items per PCT Rules and USPTO RO requirements
# ---------------------------------------------------------------------------

_FILING_CHECKLIST = [
    "PCT request form (PCT/RO/101)",
    "Filing fee (international + search fees)",
    "Specification (A4 paper format, 210mm×297mm)",
    "Claims",
    "Abstract (≤150 words)",
    "Drawings (if applicable)",
    "Designation of states",
    "Priority document (certified copy of US application)",
]

# Note included in specification metadata about A4 paper format
_A4_FORMAT_NOTE = (
    "NOTE: PCT applications must be prepared on A4 paper (210mm×297mm) with "
    "margins of at least 20mm on all sides per PCT Rule 11."
)


# ---------------------------------------------------------------------------
# Parser helpers
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


# ---------------------------------------------------------------------------
# PCTDrafter
# ---------------------------------------------------------------------------

class PCTDrafter(Drafter):
    """Drafts a PCT international patent application.

    Sends the invention description and optional prior art context to the LLM
    and parses the structured response into a DraftApplication with
    filing_format=FilingFormat.PCT.

    Key features:
    - System prompt covers PCT-specific requirements (PCT/RO/101, A4 format,
      designation of states, priority claim from US filing).
    - ads_data includes the PCT filing checklist and A4 paper format note.
    - Specification metadata notes the A4 paper format requirement.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        super().__init__(llm_provider)

    async def draft(
        self,
        invention_description: str,
        prior_art_results: list[SearchResult] | None = None,
        preferences: dict | None = None,
    ) -> DraftApplication:
        """Generate a PCT international patent application draft.

        Args:
            invention_description: Free-text description of the invention.
            prior_art_results: Optional prior art to differentiate from.
            preferences: Optional dict; recognised keys are:
                - ``claim_breadth``: "broad" | "balanced" | "narrow"
                - ``num_embodiments``: int, suggested number of embodiments
                - ``priority_application``: US application number for priority claim

        Returns:
            DraftApplication with filing_format=PCT.
        """
        prefs = preferences or {}
        log = logger.bind(
            drafter="pct",
            has_prior_art=bool(prior_art_results),
            has_preferences=bool(prefs),
        )
        log.info("pct.draft.start")

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
            log.info("pct.draft.llm_complete", tokens_used=response.tokens_used)

            parsed = _parse_llm_response(response.content)

            spec = Specification(
                background=parsed["background"] or "See detailed description.",
                summary=parsed["summary"] or "See detailed description.",
                detailed_description=parsed["detailed_description"] or "See detailed description.",
                embodiments=parsed["embodiments"],
            )

            ads_data = {
                "filing_format": "PCT",
                "paper_format": "A4 (210mm×297mm)",
                "paper_format_note": _A4_FORMAT_NOTE,
                "filing_checklist": _FILING_CHECKLIST,
            }

            if prefs.get("priority_application"):
                ads_data["priority_application"] = prefs["priority_application"]

            draft = DraftApplication(
                filing_format=FilingFormat.PCT,
                title=parsed["title"],
                abstract=parsed["abstract"] or None,
                specification=spec,
                claims=parsed["claims"],
                ads_data=ads_data,
            )

            log.info(
                "pct.draft.complete",
                title=draft.title,
                num_claims=len(draft.claims),
                num_embodiments=len(spec.embodiments),
            )
            return draft

        except Exception as exc:  # noqa: BLE001
            log.error("pct.draft.error", error=str(exc))

            spec = Specification(
                background="Draft generation failed. See error details.",
                summary="Draft generation failed. See error details.",
                detailed_description="Draft generation failed. See error details.",
                embodiments=[],
            )
            return DraftApplication(
                filing_format=FilingFormat.PCT,
                title="Draft Generation Failed",
                abstract=None,
                specification=spec,
                claims=[],
                ads_data={
                    "filing_format": "PCT",
                    "paper_format_note": _A4_FORMAT_NOTE,
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
        parts: list[str] = []

        parts.append("INVENTION DESCRIPTION:")
        parts.append(invention_description.strip())

        prior_art_context = self._build_prior_art_context(prior_art_results)
        if prior_art_context:
            parts.append("")
            parts.append(prior_art_context)

        if preferences:
            parts.append("")
            parts.append("DRAFTING PREFERENCES:")
            if "claim_breadth" in preferences:
                parts.append(f"- Claim breadth: {preferences['claim_breadth']}")
            if "num_embodiments" in preferences:
                parts.append(f"- Number of embodiments: {preferences['num_embodiments']}")
            if "priority_application" in preferences:
                parts.append(f"- Priority application: {preferences['priority_application']}")
            for key, value in preferences.items():
                if key not in ("claim_breadth", "num_embodiments", "priority_application"):
                    parts.append(f"- {key}: {value}")

        parts.append("")
        parts.append(
            "Please draft a complete PCT international patent application "
            "following the format specified in the system prompt.  Ensure the "
            "specification is formatted for A4 paper and claims provide "
            "maximum international scope."
        )

        return "\n".join(parts)
