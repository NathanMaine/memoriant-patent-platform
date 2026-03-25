"""Prior art comparison analysis module.

Sends the invention description alongside each SearchResult to an LLMProvider
and asks it to identify overlap and distinguishing features relative to the
cited prior art.  Returns a structured AnalysisResult with per-patent findings.
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
    "You are an expert patent analyst specialising in prior art comparison under "
    "35 USC 102 (novelty) and 35 USC 103 (obviousness).  "
    "When given an invention description and a prior art reference you will:\n"
    "1. Identify any overlap between the invention and the prior art.\n"
    "2. Identify features that distinguish the invention from the prior art.\n"
    "3. Assign a severity level: low (no meaningful overlap), medium (partial overlap), "
    "or high (direct anticipation or obvious variant).\n"
    "4. Suggest how the applicant should respond to or distinguish this reference.\n"
    "5. Assign an overall status: clear, caution, or conflict.\n\n"
    "Reply in EXACTLY this format (no extra text before or after):\n"
    "OVERLAP: <description or 'None'>\n"
    "DISTINGUISHING: <description>\n"
    "SEVERITY: <low|medium|high>\n"
    "SUGGESTION: <actionable suggestion>\n"
    "STATUS: <clear|caution|conflict>"
)

# ---------------------------------------------------------------------------
# Status / severity priority ordering for aggregation
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

_STATUS_MAP: dict[str, AnalysisStatus] = {
    "clear": AnalysisStatus.CLEAR,
    "caution": AnalysisStatus.CAUTION,
    "conflict": AnalysisStatus.CONFLICT,
}

_SEVERITY_MAP: dict[str, AnalysisSeverity] = {
    "low": AnalysisSeverity.LOW,
    "medium": AnalysisSeverity.MEDIUM,
    "high": AnalysisSeverity.HIGH,
}


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_llm_response(text: str) -> dict[str, str]:
    """Parse the structured LLM response into a dict of named fields."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip().upper()] = value.strip()
    return fields


# ---------------------------------------------------------------------------
# Recommendation builders
# ---------------------------------------------------------------------------

_RECOMMENDATIONS: dict[AnalysisStatus, str] = {
    AnalysisStatus.CLEAR: (
        "No prior art conflicts detected. The invention appears novel relative to the "
        "references examined. Proceed with drafting claims."
    ),
    AnalysisStatus.CAUTION: (
        "Partial overlap with one or more prior art references. Review the caution-level "
        "findings and consider narrowing or amending the relevant claims before filing."
    ),
    AnalysisStatus.CONFLICT: (
        "One or more prior art references directly anticipate or render obvious the "
        "claimed invention. Substantial claim amendments or a design-around are required."
    ),
}


# ---------------------------------------------------------------------------
# PriorArtAnalyzer
# ---------------------------------------------------------------------------

class PriorArtAnalyzer(AnalysisModule):
    """Compares an invention against a list of prior art search results."""

    module_name = "prior_art"

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    async def analyze(
        self,
        invention_description: str,
        search_results: list[SearchResult],
        claims: list[Claim] | None = None,
        specification: str | None = None,
    ) -> AnalysisResult:
        log = logger.bind(module=self.module_name, num_results=len(search_results))
        log.info("prior_art.analyze.start")

        if not search_results:
            log.info("prior_art.analyze.no_results")
            return AnalysisResult(
                module=self.module_name,
                status=AnalysisStatus.CLEAR,
                findings=[],
                recommendation=_RECOMMENDATIONS[AnalysisStatus.CLEAR],
            )

        findings: list[AnalysisFinding] = []
        worst_status = AnalysisStatus.CLEAR

        for sr in search_results:
            finding = await self._compare_one(invention_description, sr)
            findings.append(finding)

            # Escalate aggregate status if this finding is worse
            finding_status = _SEVERITY_TO_STATUS.get(finding.severity.value, AnalysisStatus.CLEAR)
            # Also respect the STATUS field parsed from the LLM response (stored in description tag)
            if _STATUS_RANK.get(finding_status, 0) > _STATUS_RANK.get(worst_status, 0):
                worst_status = finding_status

        log.info(
            "prior_art.analyze.complete",
            status=worst_status,
            num_findings=len(findings),
        )

        return AnalysisResult(
            module=self.module_name,
            status=worst_status,
            findings=findings,
            recommendation=_RECOMMENDATIONS[worst_status],
        )

    async def _compare_one(
        self,
        invention_description: str,
        search_result: SearchResult,
    ) -> AnalysisFinding:
        """Send one prior art reference to the LLM and parse the result."""
        log = logger.bind(patent_id=search_result.patent_id)

        prompt = (
            f"INVENTION DESCRIPTION:\n{invention_description}\n\n"
            f"PRIOR ART REFERENCE:\n"
            f"Patent ID: {search_result.patent_id}\n"
            f"Title: {search_result.title}\n"
        )
        if search_result.abstract:
            prompt += f"Abstract: {search_result.abstract}\n"

        try:
            log.info("prior_art.compare.start")
            response = await self.llm_provider.generate(
                prompt,
                system=_SYSTEM_PROMPT,
            )
            fields = _parse_llm_response(response.content)

            severity_str = fields.get("SEVERITY", "low").lower()
            severity = _SEVERITY_MAP.get(severity_str, AnalysisSeverity.LOW)

            # Derive per-finding status from severity for aggregation
            finding_status = _SEVERITY_TO_STATUS.get(severity_str, AnalysisStatus.CLEAR)

            description = f"[{finding_status.value.upper()}] " + (
                fields.get("OVERLAP", "Analysis complete.")
            )
            suggestion = fields.get("SUGGESTION", "Review this reference carefully.")

            log.info("prior_art.compare.done", severity=severity, status=finding_status)

            return AnalysisFinding(
                prior_art_id=search_result.patent_id,
                description=description,
                severity=severity,
                suggestion=suggestion,
                statute="35 USC 102",
            )

        except Exception as exc:  # noqa: BLE001
            log.error("prior_art.compare.error", error=str(exc))
            return AnalysisFinding(
                prior_art_id=search_result.patent_id,
                description=f"Analysis failed due to error: {exc}",
                severity=AnalysisSeverity.HIGH,
                suggestion="Retry analysis or perform manual review of this reference.",
                statute="35 USC 102",
            )
