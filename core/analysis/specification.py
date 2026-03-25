"""Specification adequacy analysis module — 35 USC 112(a).

Analyzes whether the specification satisfies the enablement and written
description requirements: (1) can a skilled person make and use the invention
from the description, and (2) does the specification adequately describe the
claimed invention?
"""
from __future__ import annotations

import structlog

from core.llm.base import LLMProvider
from core.models.patent import Claim, SearchResult
from core.analysis.base import (
    AnalysisFinding,
    AnalysisModule,
    AnalysisResult,
    AnalysisSeverity,
    AnalysisStatus,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert patent analyst specialising in specification requirements "
    "under 35 USC 112(a). The specification must satisfy two distinct requirements:\n\n"
    "1. ENABLEMENT: The specification must teach a person of ordinary skill in the art "
    "(POSITA) how to make and use the full scope of the claimed invention without "
    "undue experimentation (Wands factors). Consider breadth of claims, nature of "
    "the invention, amount of direction, presence of working examples, and predictability.\n\n"
    "2. WRITTEN DESCRIPTION: The specification must demonstrate that the inventor "
    "had possession of the claimed invention at the time of filing. The disclosure "
    "must describe each claim element and their interrelationships.\n\n"
    "When given a patent claim and a specification excerpt you will:\n"
    "1. Determine whether the specification enables the full scope of the claim.\n"
    "2. Determine whether the specification provides written description support for "
    "every claimed element.\n"
    "3. Identify any claim elements not adequately supported.\n"
    "4. Assign a severity level: low (fully supported), medium (partial support), "
    "or high (insufficient support — likely rejection).\n"
    "5. Suggest how the applicant can address any gaps.\n"
    "6. Assign an overall status: clear, caution, or conflict.\n\n"
    "Reply in EXACTLY this format (no extra text before or after):\n"
    "ENABLEMENT: <Yes|No|Possibly>\n"
    "WRITTEN_DESCRIPTION: <Supported|Not supported|Partially supported>\n"
    "ISSUES: <specific issues or 'None'>\n"
    "SEVERITY: <low|medium|high>\n"
    "SUGGESTION: <actionable suggestion>\n"
    "STATUS: <clear|caution|conflict>"
)

# ---------------------------------------------------------------------------
# Status / severity helpers
# ---------------------------------------------------------------------------

_STATUS_RANK: dict[AnalysisStatus, int] = {
    AnalysisStatus.CLEAR: 0,
    AnalysisStatus.CAUTION: 1,
    AnalysisStatus.CONFLICT: 2,
}

_SEVERITY_TO_STATUS: dict[str, AnalysisStatus] = {
    "low": AnalysisStatus.CLEAR,
    "medium": AnalysisStatus.CAUTION,
    "high": AnalysisStatus.CONFLICT,
}

_SEVERITY_MAP: dict[str, AnalysisSeverity] = {
    "low": AnalysisSeverity.LOW,
    "medium": AnalysisSeverity.MEDIUM,
    "high": AnalysisSeverity.HIGH,
}

_RECOMMENDATIONS: dict[AnalysisStatus, str] = {
    AnalysisStatus.CLEAR: (
        "Specification appears to satisfy 35 USC 112(a) requirements. Enablement "
        "and written description support are adequate for the claims as drafted."
    ),
    AnalysisStatus.CAUTION: (
        "Potential specification support issues identified. Review caution findings "
        "and consider supplementing the specification with additional examples or "
        "detailed descriptions of the affected claim elements before filing."
    ),
    AnalysisStatus.CONFLICT: (
        "Specification likely fails to satisfy 35 USC 112(a). Claims may exceed the "
        "scope of the disclosure or require undue experimentation. Narrow the claims "
        "to match supported embodiments or substantially expand the specification."
    ),
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse_llm_response(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip().upper()] = value.strip()
    return fields


# ---------------------------------------------------------------------------
# SpecificationAnalyzer
# ---------------------------------------------------------------------------

class SpecificationAnalyzer(AnalysisModule):
    """Checks specification adequacy (enablement + written description) under 35 USC 112(a)."""

    module_name = "specification"

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    async def analyze(
        self,
        invention_description: str,
        search_results: list[SearchResult],
        claims: list[Claim] | None = None,
        specification: str | None = None,
    ) -> AnalysisResult:
        log = logger.bind(
            module=self.module_name,
            num_claims=len(claims) if claims else 0,
            has_specification=specification is not None,
        )
        log.info("specification.analyze.start")

        effective_claims = claims or []

        if not effective_claims or not specification:
            log.info("specification.analyze.no_input")
            return AnalysisResult(
                module=self.module_name,
                status=AnalysisStatus.CLEAR,
                findings=[],
                recommendation=_RECOMMENDATIONS[AnalysisStatus.CLEAR],
            )

        findings: list[AnalysisFinding] = []
        worst_status = AnalysisStatus.CLEAR

        for claim in effective_claims:
            finding = await self._analyze_claim(claim, specification)
            findings.append(finding)

            finding_status = _SEVERITY_TO_STATUS.get(finding.severity.value, AnalysisStatus.CLEAR)
            if _STATUS_RANK.get(finding_status, 0) > _STATUS_RANK.get(worst_status, 0):
                worst_status = finding_status

        log.info(
            "specification.analyze.complete",
            status=worst_status,
            num_findings=len(findings),
        )

        return AnalysisResult(
            module=self.module_name,
            status=worst_status,
            findings=findings,
            recommendation=_RECOMMENDATIONS[worst_status],
        )

    async def _analyze_claim(
        self,
        claim: Claim,
        specification: str,
    ) -> AnalysisFinding:
        """Check one claim against the specification for 112(a) compliance."""
        log = logger.bind(claim_number=claim.number)

        prompt = (
            f"CLAIM {claim.number} ({claim.type}):\n{claim.text}\n\n"
            f"SPECIFICATION:\n{specification}\n"
        )

        try:
            log.info("specification.check.start")
            response = await self.llm_provider.generate(
                prompt,
                system=_SYSTEM_PROMPT,
            )
            fields = _parse_llm_response(response.content)

            severity_str = fields.get("SEVERITY", "low").lower()
            severity = _SEVERITY_MAP.get(severity_str, AnalysisSeverity.LOW)
            finding_status = _SEVERITY_TO_STATUS.get(severity_str, AnalysisStatus.CLEAR)

            issues = fields.get("ISSUES", "No issues identified.")
            description = f"[{finding_status.value.upper()}] Claim {claim.number}: {issues}"
            suggestion = fields.get("SUGGESTION", "Review specification support for this claim.")

            log.info("specification.check.done", severity=severity, status=finding_status)

            return AnalysisFinding(
                prior_art_id=None,
                description=description,
                severity=severity,
                suggestion=suggestion,
                statute="35 USC 112(a)",
            )

        except Exception as exc:  # noqa: BLE001
            log.error("specification.check.error", error=str(exc))
            return AnalysisFinding(
                prior_art_id=None,
                description=f"Analysis failed due to error: {exc}",
                severity=AnalysisSeverity.HIGH,
                suggestion="Retry analysis or perform manual review of this claim's specification support.",
                statute="35 USC 112(a)",
            )
