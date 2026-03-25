"""Patent eligibility analysis module — 35 USC 101.

Applies the Alice/Mayo two-step test to determine whether claims are directed
to patent-eligible subject matter:
  Step 1 — Is the claim directed to an abstract idea, law of nature, or
            natural phenomenon?
  Step 2 — If yes, does the claim recite "significantly more" than the
            abstract idea itself?
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
    "You are an expert patent analyst specialising in patent eligibility under "
    "35 USC 101 and the Alice/Mayo two-step framework. "
    "Under 35 USC 101, claims must be directed to a process, machine, manufacture, "
    "or composition of matter. Abstract ideas, laws of nature, and natural phenomena "
    "are judicial exceptions and are not patent-eligible unless the claim recites "
    "'significantly more'.\n\n"
    "Apply the Alice/Mayo two-step test:\n"
    "STEP 1 (Step 2A, Prong 1): Is the claim directed to a judicial exception — "
    "an abstract idea (e.g., mathematical concepts, mental processes, methods of "
    "organizing human activity), a law of nature, or a natural phenomenon?\n\n"
    "STEP 2 (Step 2A, Prong 2 and Step 2B): If yes, does the claim integrate the "
    "exception into a practical application, or does it recite additional elements "
    "that amount to 'significantly more' than the exception itself? "
    "Routine or conventional computer implementation is NOT significantly more.\n\n"
    "When analyzing a patent claim you will:\n"
    "1. Identify whether the claim is directed to a judicial exception.\n"
    "2. Evaluate whether the claim recites significantly more or a practical application.\n"
    "3. Identify specific claim elements that raise or resolve eligibility concerns.\n"
    "4. Assign a severity level: low (clearly eligible), medium (eligibility uncertain), "
    "or high (likely ineligible — Alice/Mayo rejection expected).\n"
    "5. Suggest how the applicant can amend the claim to improve eligibility.\n"
    "6. Assign an overall status: clear, caution, or conflict.\n\n"
    "Reply in EXACTLY this format (no extra text before or after):\n"
    "ABSTRACT_IDEA: <Yes|No|Possibly>\n"
    "STEP_ONE: <analysis of whether claim is directed to judicial exception>\n"
    "STEP_TWO: <analysis of significantly more or practical application>\n"
    "SIGNIFICANTLY_MORE: <present|not present|unclear>\n"
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
        "Claims appear patent-eligible under 35 USC 101. No Alice/Mayo concerns "
        "identified. Proceed with filing."
    ),
    AnalysisStatus.CAUTION: (
        "Potential eligibility concerns under 35 USC 101. Review the caution findings "
        "and consider adding specific technical implementation details or tying the "
        "abstract concept to a particular machine or transformation before filing."
    ),
    AnalysisStatus.CONFLICT: (
        "One or more claims are likely directed to patent-ineligible subject matter "
        "under 35 USC 101 (Alice/Mayo). Substantial claim amendments are required — "
        "add specific technical features that amount to significantly more than the "
        "abstract idea, or pivot to apparatus claims tied to concrete hardware."
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
# EligibilityAnalyzer
# ---------------------------------------------------------------------------

class EligibilityAnalyzer(AnalysisModule):
    """Applies the Alice/Mayo two-step test to assess 35 USC 101 eligibility."""

    module_name = "eligibility"

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
        log.info("eligibility.analyze.start")

        effective_claims = claims or []

        if not effective_claims:
            log.info("eligibility.analyze.no_claims")
            return AnalysisResult(
                module=self.module_name,
                status=AnalysisStatus.CLEAR,
                findings=[],
                recommendation=_RECOMMENDATIONS[AnalysisStatus.CLEAR],
            )

        findings: list[AnalysisFinding] = []
        worst_status = AnalysisStatus.CLEAR

        for claim in effective_claims:
            finding = await self._analyze_claim(claim, invention_description)
            findings.append(finding)

            finding_status = _SEVERITY_TO_STATUS.get(finding.severity.value, AnalysisStatus.CLEAR)
            if _STATUS_RANK.get(finding_status, 0) > _STATUS_RANK.get(worst_status, 0):
                worst_status = finding_status

        log.info(
            "eligibility.analyze.complete",
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
        invention_description: str,
    ) -> AnalysisFinding:
        """Apply Alice/Mayo two-step test to a single claim."""
        log = logger.bind(claim_number=claim.number)

        prompt = (
            f"INVENTION CONTEXT:\n{invention_description}\n\n"
            f"CLAIM {claim.number} ({claim.type}):\n{claim.text}\n"
        )

        try:
            log.info("eligibility.check.start")
            response = await self.llm_provider.generate(
                prompt,
                system=_SYSTEM_PROMPT,
            )
            fields = _parse_llm_response(response.content)

            severity_str = fields.get("SEVERITY", "low").lower()
            severity = _SEVERITY_MAP.get(severity_str, AnalysisSeverity.LOW)
            finding_status = _SEVERITY_TO_STATUS.get(severity_str, AnalysisStatus.CLEAR)

            step_one = fields.get("STEP_ONE", "No eligibility concerns.")
            description = f"[{finding_status.value.upper()}] Claim {claim.number}: {step_one}"
            suggestion = fields.get("SUGGESTION", "Review claim for abstract idea issues.")

            log.info("eligibility.check.done", severity=severity, status=finding_status)

            return AnalysisFinding(
                prior_art_id=None,
                description=description,
                severity=severity,
                suggestion=suggestion,
                statute="35 USC 101",
            )

        except Exception as exc:  # noqa: BLE001
            log.error("eligibility.check.error", error=str(exc))
            return AnalysisFinding(
                prior_art_id=None,
                description=f"Analysis failed due to error: {exc}",
                severity=AnalysisSeverity.HIGH,
                suggestion="Retry analysis or perform manual review of this claim's eligibility.",
                statute="35 USC 101",
            )
