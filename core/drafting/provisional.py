"""Provisional patent application drafter.

Generates a USPTO provisional application (35 USC 111(b)) from an invention
description and optional prior art context.  The output establishes a priority
date and should contain a written description sufficient to support future
non-provisional claims.
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
    "You are an expert patent attorney specialising in USPTO provisional patent "
    "applications under 35 USC 111(b).\n\n"
    "KEY RULES FOR PROVISIONAL APPLICATIONS:\n"
    "1. A provisional application establishes a priority date but does NOT itself "
    "issue as a patent.\n"
    "2. The written description must be sufficiently detailed to support the claims "
    "that will appear in the later non-provisional application.\n"
    "3. Drawings descriptions are strongly recommended to supplement the written "
    "description.\n"
    "4. No formal claims are required, but including recommended claims provides "
    "stronger protection and guides the written description.\n"
    "5. A cover sheet (USPTO form PTO/SB/16) is required for filing.\n\n"
    "OUTPUT FORMAT — reply in EXACTLY this structure (use the exact section headings):\n"
    "TITLE: <invention title>\n\n"
    "ABSTRACT:\n<≤150-word abstract>\n\n"
    "BACKGROUND:\n<background of the invention, problems in the prior art>\n\n"
    "SUMMARY:\n<summary of the invention>\n\n"
    "DETAILED_DESCRIPTION:\n<detailed description enabling a skilled person to make "
    "and use the invention>\n\n"
    "EMBODIMENT 1:\n"
    "Title: <short title>\n"
    "Description: <description of this embodiment>\n\n"
    "(Add EMBODIMENT 2:, EMBODIMENT 3:, etc. as needed.)\n\n"
    "CLAIM 1 (independent):\n<claim text>\n\n"
    "CLAIM 2 (dependent on 1):\n<claim text>\n\n"
    "(Add further claims as needed.)\n\n"
    "Do not include any text outside this structure."
)

# Filing checklist per USPTO requirements for provisional applications.
_FILING_CHECKLIST = [
    "Cover sheet (PTO/SB/16)",
    "Filing fee",
    "Specification",
    "Drawings (if applicable)",
]


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
    """Extract and truncate abstract to ≤150 words."""
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

        # Determine type and depends_on
        if "independent" in type_raw:
            claim_type = "independent"
            depends_on = None
        else:
            claim_type = "dependent"
            # Try to extract "on N" or "on claim N"
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
    _ALL_HEADERS = [
        "TITLE", "ABSTRACT", "BACKGROUND", "SUMMARY",
        "DETAILED_DESCRIPTION", "EMBODIMENT", "CLAIM",
    ]

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
# ProvisionalDrafter
# ---------------------------------------------------------------------------

class ProvisionalDrafter(Drafter):
    """Drafts a USPTO provisional patent application.

    Sends the invention description and optional prior art context to the LLM
    and parses the structured response into a DraftApplication with
    filing_format=FilingFormat.PROVISIONAL.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        super().__init__(llm_provider)

    async def draft(
        self,
        invention_description: str,
        prior_art_results: list[SearchResult] | None = None,
        preferences: dict | None = None,
    ) -> DraftApplication:
        """Generate a provisional patent application draft.

        Args:
            invention_description: Free-text description of the invention.
            prior_art_results: Optional prior art to differentiate from.
            preferences: Optional dict; recognised keys are:
                - ``claim_breadth``: "broad" | "moderate" | "narrow"
                - ``num_embodiments``: int, suggested number of embodiments

        Returns:
            DraftApplication with filing_format=PROVISIONAL.
        """
        log = logger.bind(
            drafter="provisional",
            has_prior_art=bool(prior_art_results),
            has_preferences=bool(preferences),
        )
        log.info("provisional.draft.start")

        prompt = self._build_prompt(
            invention_description=invention_description,
            prior_art_results=prior_art_results,
            preferences=preferences or {},
        )

        try:
            response = await self.llm_provider.generate(
                prompt,
                system=_SYSTEM_PROMPT,
                max_tokens=4096,
            )
            log.info("provisional.draft.llm_complete", tokens_used=response.tokens_used)

            parsed = _parse_llm_response(response.content)

            spec = Specification(
                background=parsed["background"] or "See detailed description.",
                summary=parsed["summary"] or "See detailed description.",
                detailed_description=parsed["detailed_description"] or "See detailed description.",
                embodiments=parsed["embodiments"],
            )

            draft = DraftApplication(
                filing_format=FilingFormat.PROVISIONAL,
                title=parsed["title"],
                abstract=parsed["abstract"] or None,
                specification=spec,
                claims=parsed["claims"],
                ads_data={"filing_checklist": _FILING_CHECKLIST},
            )

            log.info(
                "provisional.draft.complete",
                title=draft.title,
                num_claims=len(draft.claims),
                num_embodiments=len(spec.embodiments),
            )
            return draft

        except Exception as exc:  # noqa: BLE001
            log.error("provisional.draft.error", error=str(exc))

            # Return a partial / error result rather than propagating.
            spec = Specification(
                background="Draft generation failed. See error details.",
                summary="Draft generation failed. See error details.",
                detailed_description="Draft generation failed. See error details.",
                embodiments=[],
            )
            return DraftApplication(
                filing_format=FilingFormat.PROVISIONAL,
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
            for key, value in preferences.items():
                if key not in ("claim_breadth", "num_embodiments"):
                    parts.append(f"- {key}: {value}")

        parts.append("")
        parts.append(
            "Please draft a complete provisional patent application following the "
            "format specified in the system prompt."
        )

        return "\n".join(parts)
