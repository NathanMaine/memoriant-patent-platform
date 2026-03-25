"""Formalities analysis module — MPEP 608.

All checks are rule-based; no LLM call is required (or made) in v1.
An optional LLMProvider is accepted in the constructor for future
nuanced checks but is unused in the current implementation.

Checks performed:
    1. Abstract length ≤ 150 words
    2. Title length < 500 characters
    3. Claims numbered sequentially starting from 1
    4. Dependent claims reference a valid (existing) claim number
    5. At least one independent claim present
    6. Specification sections (background, summary, detailed_description) non-empty
    7. At least one embodiment in the specification
"""
from __future__ import annotations

import structlog

from core.llm.base import LLMProvider
from core.models.patent import Claim, SearchResult
from core.models.application import DraftApplication, Specification
from core.analysis.base import (
    AnalysisFinding,
    AnalysisModule,
    AnalysisResult,
    AnalysisSeverity,
    AnalysisStatus,
)

logger = structlog.get_logger(__name__)

_STATUTE = "MPEP 608"

# How many findings of each severity push the overall status up.
_STATUS_RANK: dict[AnalysisStatus, int] = {
    AnalysisStatus.CLEAR: 0,
    AnalysisStatus.CAUTION: 1,
    AnalysisStatus.CONFLICT: 2,
}

_RECOMMENDATIONS: dict[AnalysisStatus, str] = {
    AnalysisStatus.CLEAR: (
        "All MPEP 608 formalities checks passed. The application appears formally "
        "compliant for filing."
    ),
    AnalysisStatus.CAUTION: (
        "One or more formalities issues were identified under MPEP 608. Review the "
        "findings and correct before filing to avoid an examiner objection."
    ),
    AnalysisStatus.CONFLICT: (
        "Multiple or serious formalities deficiencies identified under MPEP 608. "
        "Significant corrections are required before this application can be filed."
    ),
}


def _finding(description: str, suggestion: str, severity: AnalysisSeverity) -> AnalysisFinding:
    return AnalysisFinding(
        prior_art_id=None,
        description=description,
        severity=severity,
        suggestion=suggestion,
        statute=_STATUTE,
    )


class FormalitiesAnalyzer(AnalysisModule):
    """Rule-based formalities checker under MPEP 608.

    Constructor Parameters
    ----------------------
    llm_provider:
        Optional LLMProvider reserved for future nuanced checks.
        Unused in v1 — all checks are purely rule-based.
    """

    module_name = "formalities"

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def analyze(
        self,
        invention_description: str,
        search_results: list[SearchResult],
        claims: list[Claim] | None = None,
        specification: Specification | None = None,
        abstract: str | None = None,
        title: str | None = None,
        draft_application: DraftApplication | None = None,
    ) -> AnalysisResult:
        """Run all MPEP 608 formality checks and return an AnalysisResult.

        Parameters
        ----------
        invention_description:
            Plain-text description of the invention (logged but not checked here).
        search_results:
            Prior art search results — ignored for formalities analysis.
        claims:
            Explicit list of claims. Overridden by draft_application if provided.
        specification:
            Explicit Specification object. Overridden by draft_application if provided.
        abstract:
            Explicit abstract string. Overridden by draft_application if provided.
        title:
            Explicit title string. Overridden by draft_application if provided.
        draft_application:
            If provided, claims/specification/abstract/title are extracted from it.
        """
        # Extract fields from DraftApplication when present
        if draft_application is not None:
            claims = draft_application.claims
            specification = draft_application.specification
            abstract = draft_application.abstract
            title = draft_application.title

        log = logger.bind(
            module=self.module_name,
            num_claims=len(claims) if claims else 0,
            has_abstract=abstract is not None,
        )
        log.info("formalities.analyze.start")

        findings: list[AnalysisFinding] = []

        findings.extend(self._check_abstract(abstract))
        findings.extend(self._check_title(title))
        findings.extend(self._check_claims(claims or []))
        if specification is not None:
            findings.extend(self._check_specification(specification))

        # Determine overall status from findings.
        # HIGH severity → CONFLICT; any other severity → CAUTION at minimum.
        _sev_to_status: dict[AnalysisSeverity, AnalysisStatus] = {
            AnalysisSeverity.HIGH: AnalysisStatus.CONFLICT,
            AnalysisSeverity.MEDIUM: AnalysisStatus.CAUTION,
            AnalysisSeverity.LOW: AnalysisStatus.CAUTION,
        }
        worst = AnalysisStatus.CLEAR
        for finding in findings:
            candidate = _sev_to_status.get(finding.severity, AnalysisStatus.CAUTION)
            if _STATUS_RANK[candidate] > _STATUS_RANK[worst]:
                worst = candidate

        # Escalate to CONFLICT when there are 3 or more findings
        if len(findings) >= 3 and worst == AnalysisStatus.CAUTION:
            worst = AnalysisStatus.CONFLICT

        log.info(
            "formalities.analyze.complete",
            status=worst,
            num_findings=len(findings),
        )

        return AnalysisResult(
            module=self.module_name,
            status=worst,
            findings=findings,
            recommendation=_RECOMMENDATIONS[worst],
        )

    # ------------------------------------------------------------------
    # Rule implementations
    # ------------------------------------------------------------------

    def _check_abstract(self, abstract: str | None) -> list[AnalysisFinding]:
        """Rule 1: Abstract must be present and ≤ 150 words."""
        findings: list[AnalysisFinding] = []

        if abstract is None or abstract.strip() == "":
            findings.append(_finding(
                description="Abstract is missing. An abstract is required for a patent application.",
                suggestion=(
                    "Add a concise abstract of no more than 150 words that summarizes the "
                    "nature, purpose, and distinguishing features of the invention."
                ),
                severity=AnalysisSeverity.HIGH,
            ))
            return findings

        word_count = len(abstract.split())
        if word_count > 150:
            findings.append(_finding(
                description=(
                    f"Abstract exceeds 150 words ({word_count} words). Under MPEP 608.01(b), "
                    "the abstract must not exceed 150 words."
                ),
                suggestion=(
                    f"Reduce the abstract from {word_count} words to 150 words or fewer. "
                    "Focus on the novel features and principal utility of the invention."
                ),
                severity=AnalysisSeverity.MEDIUM,
            ))

        return findings

    def _check_title(self, title: str | None) -> list[AnalysisFinding]:
        """Rule 2: Title should be under 500 characters."""
        findings: list[AnalysisFinding] = []

        if title is None or title.strip() == "":
            findings.append(_finding(
                description="Title is missing. A title is required for a patent application.",
                suggestion="Add a concise, descriptive title for the invention.",
                severity=AnalysisSeverity.HIGH,
            ))
            return findings

        if len(title) > 500:
            findings.append(_finding(
                description=(
                    f"Title exceeds 500 characters ({len(title)} characters). "
                    "Under MPEP 608.01(a), the title should be short and specific."
                ),
                suggestion=(
                    f"Shorten the title from {len(title)} characters to under 500 characters. "
                    "The title should be descriptive but concise."
                ),
                severity=AnalysisSeverity.MEDIUM,
            ))

        return findings

    def _check_claims(self, claims: list[Claim]) -> list[AnalysisFinding]:
        """Rules 3, 4, 5: Numbering, dependent-claim references, independent claims."""
        findings: list[AnalysisFinding] = []

        if not claims:
            return findings

        # Rule 3: Sequential numbering starting from 1
        numbers = [c.number for c in claims]
        expected = list(range(1, len(numbers) + 1))
        if numbers != expected:
            findings.append(_finding(
                description=(
                    f"Claim numbering is not sequential starting from 1. "
                    f"Found numbers: {numbers}; expected: {expected}."
                ),
                suggestion=(
                    "Renumber claims sequentially starting from 1. Each claim must be "
                    "assigned a unique Arabic numeral in consecutive order."
                ),
                severity=AnalysisSeverity.HIGH,
            ))

        # Rule 4: Dependent claims reference existing claim numbers
        claim_numbers = {c.number for c in claims}
        for claim in claims:
            if claim.type == "dependent" and claim.depends_on is not None:
                if claim.depends_on not in claim_numbers:
                    findings.append(_finding(
                        description=(
                            f"Dependent claim {claim.number} references claim {claim.depends_on}, "
                            "which does not exist in this application."
                        ),
                        suggestion=(
                            f"Update claim {claim.number} to reference an existing claim number, "
                            f"or add the missing claim {claim.depends_on} to the application."
                        ),
                        severity=AnalysisSeverity.HIGH,
                    ))

        # Rule 5: At least one independent claim
        independent_claims = [c for c in claims if c.type == "independent"]
        if not independent_claims:
            findings.append(_finding(
                description=(
                    "No independent claims found. Every patent application must contain "
                    "at least one independent claim."
                ),
                suggestion=(
                    "Add at least one independent claim that defines the broadest scope of "
                    "the invention without referencing any other claim."
                ),
                severity=AnalysisSeverity.HIGH,
            ))

        return findings

    def _check_specification(self, specification: Specification) -> list[AnalysisFinding]:
        """Rules 6, 7: Non-empty specification sections and at least one embodiment."""
        findings: list[AnalysisFinding] = []

        # Rule 6: Non-empty sections
        sections = [
            ("background", specification.background, "Background of the Invention"),
            ("summary", specification.summary, "Summary of the Invention"),
            ("detailed_description", specification.detailed_description, "Detailed Description"),
        ]
        for field_name, content, display_name in sections:
            if not content or not content.strip():
                findings.append(_finding(
                    description=(
                        f"Specification section '{display_name}' is empty. "
                        "Under MPEP 608.01, all major specification sections should be present "
                        "and contain substantive content."
                    ),
                    suggestion=(
                        f"Add substantive content to the '{display_name}' section. "
                        "This section helps examiners and courts understand the invention."
                    ),
                    severity=AnalysisSeverity.MEDIUM,
                ))

        # Rule 7: At least one embodiment
        if not specification.embodiments:
            findings.append(_finding(
                description=(
                    "Specification contains no embodiments. At least one embodiment of the "
                    "invention should be described to satisfy MPEP 608.01."
                ),
                suggestion=(
                    "Add at least one detailed embodiment describing how the invention can be "
                    "made and used. Multiple embodiments strengthen the disclosure."
                ),
                severity=AnalysisSeverity.MEDIUM,
            ))

        return findings
