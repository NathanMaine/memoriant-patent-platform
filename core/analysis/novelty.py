"""Novelty analysis module — 35 USC 102.

Checks each claim against each prior art reference to determine whether a
single reference anticipates the claim by disclosing every element.
Returns a structured AnalysisResult with per-reference findings.
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
    "You are an expert patent analyst specialising in novelty under 35 USC 102. "
    "Under 35 USC 102, a claim lacks novelty (is 'anticipated') if a SINGLE prior art "
    "reference discloses EVERY element of the claim, either expressly or inherently. "
    "When given a patent claim and a prior art reference you will:\n"
    "1. Determine whether the reference anticipates the claim by disclosing every element.\n"
    "2. Identify any claim elements missing from the reference.\n"
    "3. Assign a severity level: low (reference does not anticipate), "
    "medium (reference discloses most elements — close call), "
    "or high (reference anticipates all elements).\n"
    "4. Suggest how the applicant can distinguish the reference.\n"
    "5. Assign an overall status: clear, caution, or conflict.\n\n"
    "Reply in EXACTLY this format (no extra text before or after):\n"
    "ANTICIPATED: <Yes|No|Partially>\n"
    "MISSING_ELEMENTS: <list of missing elements or 'None'>\n"
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
        "No anticipation detected under 35 USC 102. Each claim appears novel over the "
        "references examined. Proceed with filing."
    ),
    AnalysisStatus.CAUTION: (
        "One or more references closely approach the claimed invention. Review caution "
        "findings and consider narrowing affected claims before filing."
    ),
    AnalysisStatus.CONFLICT: (
        "One or more claims appear to be anticipated by a single prior art reference "
        "under 35 USC 102. Claim amendments or a design-around are required."
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
# NoveltyAnalyzer
# ---------------------------------------------------------------------------

class NoveltyAnalyzer(AnalysisModule):
    """Checks each claim against prior art references for 35 USC 102 novelty."""

    module_name = "novelty"

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
        log.info("novelty.analyze.start")

        effective_claims = claims or []

        if not search_results or not effective_claims:
            log.info("novelty.analyze.no_input")
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
            "novelty.analyze.complete",
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
        """Compare the claim set against one prior art reference."""
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
            log.info("novelty.compare.start")
            response = await self.llm_provider.generate(
                prompt,
                system=_SYSTEM_PROMPT,
            )
            fields = _parse_llm_response(response.content)

            severity_str = fields.get("SEVERITY", "low").lower()
            severity = _SEVERITY_MAP.get(severity_str, AnalysisSeverity.LOW)
            finding_status = _SEVERITY_TO_STATUS.get(severity_str, AnalysisStatus.CLEAR)

            description = f"[{finding_status.value.upper()}] " + (
                fields.get("MISSING_ELEMENTS", "Analysis complete.")
            )
            suggestion = fields.get("SUGGESTION", "Review this reference carefully.")

            log.info("novelty.compare.done", severity=severity, status=finding_status)

            return AnalysisFinding(
                prior_art_id=search_result.patent_id,
                description=description,
                severity=severity,
                suggestion=suggestion,
                statute="35 USC 102",
            )

        except Exception as exc:  # noqa: BLE001
            log.error("novelty.compare.error", error=str(exc))
            return AnalysisFinding(
                prior_art_id=search_result.patent_id,
                description=f"Analysis failed due to error: {exc}",
                severity=AnalysisSeverity.HIGH,
                suggestion="Retry analysis or perform manual review of this reference.",
                statute="35 USC 102",
            )
