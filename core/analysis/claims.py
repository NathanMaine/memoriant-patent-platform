"""Claims definiteness analysis module — 35 USC 112(b).

Analyzes each claim for definiteness: clear language, no ambiguous terms,
proper antecedent basis, and each term defined or well-understood in the art.
Does not require prior art search results — operates directly on claim text.
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
    "You are an expert patent analyst specialising in claim definiteness under "
    "35 USC 112(b). Under 35 USC 112(b), claims must particularly point out and "
    "distinctly claim the subject matter of the invention. A claim is indefinite if "
    "it does not inform those skilled in the art about the scope of the invention "
    "with reasonable certainty (Nautilus v. Biosig, 2014). "
    "When analyzing a patent claim you will check for:\n"
    "1. Ambiguous or subjective terms (e.g., 'substantially', 'about', 'optimum') "
    "without supporting definition in the specification.\n"
    "2. Antecedent basis issues — each 'said' or 'the' reference must have a prior "
    "introduction of the element.\n"
    "3. Terms that render the claim scope unclear or undetermined.\n"
    "4. Mixed-class claims or improper functional claim language.\n"
    "5. Assign a severity level: low (no issues), medium (minor issues), "
    "or high (claim likely indefinite).\n"
    "6. Suggest corrections.\n"
    "7. Assign an overall status: clear, caution, or conflict.\n\n"
    "Reply in EXACTLY this format (no extra text before or after):\n"
    "INDEFINITE: <Yes|No|Possibly>\n"
    "ISSUES: <description of issues or 'None'>\n"
    "ANTECEDENT_BASIS: <antecedent basis analysis>\n"
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
        "All claims appear definite under 35 USC 112(b). Claim language is clear "
        "with proper antecedent basis and no ambiguous terms identified."
    ),
    AnalysisStatus.CAUTION: (
        "Potential definiteness issues identified in one or more claims. Review the "
        "caution findings and consider amending claim language or adding definitions "
        "to the specification before filing."
    ),
    AnalysisStatus.CONFLICT: (
        "One or more claims appear indefinite under 35 USC 112(b). Substantial claim "
        "redrafting is required to clearly define the scope of the invention."
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
# ClaimsAnalyzer
# ---------------------------------------------------------------------------

class ClaimsAnalyzer(AnalysisModule):
    """Analyzes patent claims for definiteness under 35 USC 112(b)."""

    module_name = "claims"

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
        )
        log.info("claims.analyze.start")

        effective_claims = claims or []

        if not effective_claims:
            log.info("claims.analyze.no_claims")
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
            "claims.analyze.complete",
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
        specification: str | None,
    ) -> AnalysisFinding:
        """Send one claim to the LLM for definiteness analysis."""
        log = logger.bind(claim_number=claim.number)

        prompt = f"CLAIM {claim.number} ({claim.type}):\n{claim.text}\n"
        if specification:
            prompt += f"\nSPECIFICATION EXCERPT:\n{specification}\n"

        try:
            log.info("claims.check.start")
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
            suggestion = fields.get("SUGGESTION", "Review claim language for clarity.")

            log.info("claims.check.done", severity=severity, status=finding_status)

            return AnalysisFinding(
                prior_art_id=None,
                description=description,
                severity=severity,
                suggestion=suggestion,
                statute="35 USC 112(b)",
            )

        except Exception as exc:  # noqa: BLE001
            log.error("claims.check.error", error=str(exc))
            return AnalysisFinding(
                prior_art_id=None,
                description=f"Analysis failed due to error: {exc}",
                severity=AnalysisSeverity.HIGH,
                suggestion="Retry analysis or perform manual review of this claim.",
                statute="35 USC 112(b)",
            )
