"""Patent Quality Scoring Service.

Assesses the overall quality and strength of a patent application by evaluating
six weighted dimensions using an LLM, producing a numerical score and breakdown.
"""
from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from core.llm.base import LLMProvider
from core.models.application import DraftApplication
from core.analysis.base import AnalysisResult

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class QualityDimension(BaseModel):
    """A single scored dimension of patent quality."""

    name: str          # e.g., "claim_breadth", "specification_depth"
    score: float       # 0.0 – 10.0
    weight: float      # relative importance (all weights sum to 1.0)
    notes: str         # explanation from the LLM


class PatentQualityScore(BaseModel):
    """Aggregated quality assessment of a patent application."""

    overall_score: float            # 0.0 – 100.0
    grade: str                      # A, B, C, D, F
    dimensions: list[QualityDimension]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]


# ---------------------------------------------------------------------------
# Dimension definitions
# ---------------------------------------------------------------------------

_DIMENSIONS: list[dict] = [
    {
        "name": "claim_breadth",
        "weight": 0.25,
        "description": (
            "Are the independent claims drafted as broadly as the prior art allows? "
            "Are there dependent claims providing fallback narrower positions? "
            "A high score means the broadest reasonable scope is captured with a "
            "well-structured dependent claim hierarchy."
        ),
    },
    {
        "name": "specification_depth",
        "weight": 0.20,
        "description": (
            "Does the specification provide multiple embodiments, a detailed description, "
            "working examples, and enough disclosure to enable a person skilled in the art "
            "to practice every claimed variant? A high score means the spec clearly supports "
            "all claim scope and would survive a 35 USC 112 written description challenge."
        ),
    },
    {
        "name": "prior_art_differentiation",
        "weight": 0.20,
        "description": (
            "Do the claims and specification clearly articulate how the invention differs "
            "from prior art? Are the distinguishing features specific and verifiable? "
            "A high score means the novel contribution is explicit and the prosecution "
            "history would contain clear arguments for patentability."
        ),
    },
    {
        "name": "formalities_compliance",
        "weight": 0.10,
        "description": (
            "Does the application comply with USPTO formalities? Check abstract length "
            "(≤150 words), claim format (each claim as a single sentence, proper dependencies), "
            "consistent reference numerals, and structure (background, summary, detailed "
            "description). A high score means the application is ready to file without "
            "formality rejections."
        ),
    },
    {
        "name": "prosecution_readiness",
        "weight": 0.15,
        "description": (
            "How likely are the claims to survive 101/102/103 challenges during prosecution? "
            "Consider Alice/Mayo eligibility, novelty over prior art, and non-obviousness. "
            "A high score means the claims as drafted are defensible with minimal amendments."
        ),
    },
    {
        "name": "commercial_value",
        "weight": 0.10,
        "description": (
            "Does the patent claim a commercially significant chokepoint? Would competitors "
            "need to design around these claims or license them? A high score means the "
            "claims are strategically positioned to cover a real market opportunity."
        ),
    },
]

# Verify weights sum correctly at import time (sanity check)
assert abs(sum(d["weight"] for d in _DIMENSIONS) - 1.0) < 1e-9, "Dimension weights must sum to 1.0"

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert patent attorney and quality analyst. "
    "You will evaluate a specific quality dimension of a patent application and assign a "
    "numerical score from 0.0 (worst) to 10.0 (best). "
    "Be precise and actionable.\n\n"
    "Reply in EXACTLY this format (no extra text before or after):\n"
    "SCORE: <0.0-10.0>\n"
    "NOTES: <concise explanation of the score, 1-3 sentences>\n"
    "STRENGTHS: <one key strength for this dimension>\n"
    "WEAKNESSES: <one key weakness for this dimension, or 'None identified'>\n"
    "RECOMMENDATIONS: <one actionable recommendation, or 'None required'>"
)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse_llm_response(text: str) -> dict[str, str]:
    """Parse the structured LLM response into a key→value dict."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip().upper()] = value.strip()
    return fields


def _safe_float(value: str, default: float) -> float:
    """Convert a string to float, returning default on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# PatentQualityScorer
# ---------------------------------------------------------------------------

class PatentQualityScorer:
    """Scores the quality of a patent application across six weighted dimensions.

    Each dimension is evaluated independently by the LLM. The overall score is
    the weighted average of dimension scores scaled to 0–100.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def score_draft(
        self,
        draft: DraftApplication,
        analysis_results: list[AnalysisResult] | None = None,
    ) -> PatentQualityScore:
        """Score a draft patent application across all quality dimensions.

        Args:
            draft: The DraftApplication to evaluate.
            analysis_results: Optional prior analysis results (novelty, obviousness,
                              eligibility, etc.) that inform the scoring context.

        Returns:
            A PatentQualityScore with an overall score, grade, per-dimension
            breakdown, strengths, weaknesses, and recommendations.
        """
        log = logger.bind(
            draft_id=str(draft.id),
            num_claims=len(draft.claims),
            num_analysis_results=len(analysis_results) if analysis_results else 0,
        )
        log.info("quality_scorer.score_draft.start")

        application_context = self._build_application_context(draft, analysis_results)

        dimensions: list[QualityDimension] = []
        all_strengths: list[str] = []
        all_weaknesses: list[str] = []
        all_recommendations: list[str] = []

        for dim_def in _DIMENSIONS:
            dim_result = await self._score_dimension(
                dim_def=dim_def,
                application_context=application_context,
            )
            dimensions.append(dim_result["dimension"])
            if dim_result["strength"]:
                all_strengths.append(dim_result["strength"])
            if dim_result["weakness"] and dim_result["weakness"].lower() != "none identified":
                all_weaknesses.append(dim_result["weakness"])
            if dim_result["recommendation"] and dim_result["recommendation"].lower() != "none required":
                all_recommendations.append(dim_result["recommendation"])

        overall_score = sum(d.score * d.weight for d in dimensions) * 10.0
        overall_score = max(0.0, min(100.0, overall_score))
        grade = self._compute_grade(overall_score)

        log.info(
            "quality_scorer.score_draft.complete",
            overall_score=overall_score,
            grade=grade,
        )

        return PatentQualityScore(
            overall_score=overall_score,
            grade=grade,
            dimensions=dimensions,
            strengths=all_strengths,
            weaknesses=all_weaknesses,
            recommendations=all_recommendations,
        )

    # ------------------------------------------------------------------
    # Grade mapping
    # ------------------------------------------------------------------

    def _compute_grade(self, overall_score: float) -> str:
        """Map a 0–100 overall score to a letter grade.

        Thresholds:
            90–100 → A
            80–89  → B
            70–79  → C
            60–69  → D
            <60    → F
        """
        if overall_score >= 90.0:
            return "A"
        if overall_score >= 80.0:
            return "B"
        if overall_score >= 70.0:
            return "C"
        if overall_score >= 60.0:
            return "D"
        return "F"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _score_dimension(
        self,
        dim_def: dict,
        application_context: str,
    ) -> dict:
        """Evaluate a single quality dimension via the LLM.

        Returns a dict with keys: dimension, strength, weakness, recommendation.
        On LLM failure, returns a fallback dimension with score 0.0.
        """
        log = logger.bind(dimension=dim_def["name"])

        prompt = (
            f"QUALITY DIMENSION: {dim_def['name']}\n"
            f"EVALUATION CRITERIA:\n{dim_def['description']}\n\n"
            f"{application_context}"
        )

        try:
            log.info("quality_scorer.dimension.start")
            response = await self.llm_provider.generate(prompt, system=_SYSTEM_PROMPT)
            fields = _parse_llm_response(response.content)

            score = _safe_float(fields.get("SCORE", "0"), default=0.0)
            score = max(0.0, min(10.0, score))
            notes = fields.get("NOTES", "No notes provided.")
            strength = fields.get("STRENGTHS", "")
            weakness = fields.get("WEAKNESSES", "")
            recommendation = fields.get("RECOMMENDATIONS", "")

            log.info("quality_scorer.dimension.complete", score=score)

            return {
                "dimension": QualityDimension(
                    name=dim_def["name"],
                    score=score,
                    weight=dim_def["weight"],
                    notes=notes,
                ),
                "strength": strength,
                "weakness": weakness,
                "recommendation": recommendation,
            }

        except Exception as exc:  # noqa: BLE001
            log.error("quality_scorer.dimension.error", error=str(exc))
            return {
                "dimension": QualityDimension(
                    name=dim_def["name"],
                    score=0.0,
                    weight=dim_def["weight"],
                    notes=f"Evaluation failed: {exc}",
                ),
                "strength": "",
                "weakness": f"Could not evaluate {dim_def['name']}: {exc}",
                "recommendation": f"Retry evaluation of {dim_def['name']}.",
            }

    def _build_application_context(
        self,
        draft: DraftApplication,
        analysis_results: list[AnalysisResult] | None,
    ) -> str:
        """Build a text block summarising the draft application for the LLM."""
        lines: list[str] = [
            f"APPLICATION TITLE: {draft.title}",
        ]

        if draft.abstract:
            lines.append(f"\nABSTRACT:\n{draft.abstract}")

        lines.append(f"\nSPECIFICATION BACKGROUND:\n{draft.specification.background}")
        lines.append(f"\nSPECIFICATION SUMMARY:\n{draft.specification.summary}")

        if draft.specification.embodiments:
            lines.append(f"\nNUMBER OF EMBODIMENTS: {len(draft.specification.embodiments)}")

        if draft.claims:
            lines.append(f"\nCLAIMS ({len(draft.claims)} total):")
            for claim in draft.claims:
                dep = f" (depends on {claim.depends_on})" if claim.depends_on else ""
                lines.append(f"  Claim {claim.number} [{claim.type}{dep}]: {claim.text}")

        if analysis_results:
            lines.append(f"\nPRIOR ANALYSIS RESULTS ({len(analysis_results)} modules):")
            for ar in analysis_results:
                lines.append(f"  {ar.module.upper()}: {ar.status.value.upper()} — {ar.recommendation}")

        return "\n".join(lines)
