"""Obviousness analysis module — 35 USC 103.

Evaluates whether the claimed invention would have been obvious to a person
of ordinary skill in the art (POSITA) at the time of invention, applying the
Graham v. John Deere four-factor framework.
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
    "You are an expert patent analyst specialising in obviousness under 35 USC 103. "
    "Under 35 USC 103, a claim is obvious if the differences between the claimed invention "
    "and the prior art would have been obvious to a person of ordinary skill in the art "
    "(POSITA) at the time of the invention. "
    "Apply the Graham v. John Deere four-factor test:\n"
    "1. Scope and content of the prior art.\n"
    "2. Differences between the prior art and the claims at issue.\n"
    "3. Level of ordinary skill in the pertinent art.\n"
    "4. Secondary considerations (commercial success, long-felt need, etc.).\n\n"
    "Also consider whether combining 2-3 references would render the claims obvious. "
    "When given a patent claim and one or more prior art references you will:\n"
    "1. Determine whether the claim would be obvious over the reference(s).\n"
    "2. Identify the differences between the claim and the prior art.\n"
    "3. Evaluate whether there is motivation to combine references and a reasonable "
    "expectation of success.\n"
    "4. Assign a severity level: low (not obvious), medium (potentially obvious), "
    "or high (clearly obvious).\n"
    "5. Suggest how the applicant can rebut an obviousness rejection.\n"
    "6. Assign an overall status: clear, caution, or conflict.\n\n"
    "Reply in EXACTLY this format (no extra text before or after):\n"
    "OBVIOUS: <Yes|No|Possibly>\n"
    "DIFFERENCES: <differences between claim and prior art>\n"
    "SECONDARY_CONSIDERATIONS: <any secondary considerations or 'None'>\n"
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
        "No obviousness issues detected under 35 USC 103. The claims appear non-obvious "
        "over the references examined. Proceed with filing."
    ),
    AnalysisStatus.CAUTION: (
        "Potential obviousness concerns identified. Review the caution findings, consider "
        "adding secondary consideration evidence, and evaluate whether claim amendments "
        "could further distinguish the prior art."
    ),
    AnalysisStatus.CONFLICT: (
        "One or more claims appear obvious under 35 USC 103. Substantial claim amendments, "
        "design-around strategies, or compelling secondary consideration evidence are required."
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
# ObviousnessAnalyzer
# ---------------------------------------------------------------------------

class ObviousnessAnalyzer(AnalysisModule):
    """Evaluates claims for obviousness under 35 USC 103 using Graham factors."""

    module_name = "obviousness"

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
            num_results=len(search_results),
            num_claims=len(claims) if claims else 0,
        )
        log.info("obviousness.analyze.start")

        effective_claims = claims or []

        if not search_results or not effective_claims:
            log.info("obviousness.analyze.no_input")
            return AnalysisResult(
                module=self.module_name,
                status=AnalysisStatus.CLEAR,
                findings=[],
                recommendation=_RECOMMENDATIONS[AnalysisStatus.CLEAR],
            )

        findings: list[AnalysisFinding] = []
        worst_status = AnalysisStatus.CLEAR

        for sr in search_results:
            finding = await self._analyze_one(effective_claims, sr)
            findings.append(finding)

            finding_status = _SEVERITY_TO_STATUS.get(finding.severity.value, AnalysisStatus.CLEAR)
            if _STATUS_RANK.get(finding_status, 0) > _STATUS_RANK.get(worst_status, 0):
                worst_status = finding_status

        log.info(
            "obviousness.analyze.complete",
            status=worst_status,
            num_findings=len(findings),
        )

        return AnalysisResult(
            module=self.module_name,
            status=worst_status,
            findings=findings,
            recommendation=_RECOMMENDATIONS[worst_status],
        )

    async def _analyze_one(
        self,
        claims: list[Claim],
        search_result: SearchResult,
    ) -> AnalysisFinding:
        """Evaluate obviousness of the claim set against one prior art reference."""
        log = logger.bind(patent_id=search_result.patent_id)

        claims_text = "\n".join(
            f"Claim {c.number}: {c.text}" for c in claims
        )

        prompt = (
            f"CLAIMS TO ANALYZE:\n{claims_text}\n\n"
            f"PRIOR ART REFERENCE:\n"
            f"Patent ID: {search_result.patent_id}\n"
            f"Title: {search_result.title}\n"
        )
        if search_result.abstract:
            prompt += f"Abstract: {search_result.abstract}\n"

        try:
            log.info("obviousness.compare.start")
            response = await self.llm_provider.generate(
                prompt,
                system=_SYSTEM_PROMPT,
            )
            fields = _parse_llm_response(response.content)

            severity_str = fields.get("SEVERITY", "low").lower()
            severity = _SEVERITY_MAP.get(severity_str, AnalysisSeverity.LOW)
            finding_status = _SEVERITY_TO_STATUS.get(severity_str, AnalysisStatus.CLEAR)

            differences = fields.get("DIFFERENCES", "Analysis complete.")
            description = f"[{finding_status.value.upper()}] {differences}"
            suggestion = fields.get("SUGGESTION", "Review this reference carefully.")

            log.info("obviousness.compare.done", severity=severity, status=finding_status)

            return AnalysisFinding(
                prior_art_id=search_result.patent_id,
                description=description,
                severity=severity,
                suggestion=suggestion,
                statute="35 USC 103",
            )

        except Exception as exc:  # noqa: BLE001
            log.error("obviousness.compare.error", error=str(exc))
            return AnalysisFinding(
                prior_art_id=search_result.patent_id,
                description=f"Analysis failed due to error: {exc}",
                severity=AnalysisSeverity.HIGH,
                suggestion="Retry analysis or perform manual review of this reference.",
                statute="35 USC 103",
            )
