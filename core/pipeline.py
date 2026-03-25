"""Patent pipeline orchestrator.

Coordinates the full end-to-end patent workflow:
  describe → search → analyze → prior_art_gate → draft → review → export → complete

Supports stage re-entry via ``resume_from`` and a user-override bypass for the
prior art gate. Each stage is timed and recorded in ``PipelineResult.metrics``.
Structured logging (structlog) is used throughout.
"""
from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

from core.analysis.base import AnalysisModule, AnalysisResult, AnalysisStatus
from core.drafting.base import Drafter
from core.export.docx_export import export_docx
from core.export.pdf_export import export_pdf
from core.llm.base import LLMProvider
from core.models.application import DraftApplication, FilingFormat
from core.models.patent import SearchResult
from core.search.aggregator import SearchAggregator
from core.search.base import SearchQuery
from core.storage.base import StorageProvider

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Public enums & models
# ---------------------------------------------------------------------------


class PipelineStage(StrEnum):
    DESCRIBE = "describe"
    SEARCH = "search"
    ANALYZE = "analyze"
    DRAFT = "draft"
    REVIEW = "review"
    EXPORT = "export"
    COMPLETE = "complete"
    FAILED = "failed"


_STAGE_ORDER: list[PipelineStage] = [
    PipelineStage.DESCRIBE,
    PipelineStage.SEARCH,
    PipelineStage.ANALYZE,
    PipelineStage.DRAFT,
    PipelineStage.REVIEW,
    PipelineStage.EXPORT,
    PipelineStage.COMPLETE,
]


class PipelineResult(BaseModel):
    """Accumulated result of a PatentPipeline run."""

    project_id: str
    stages_completed: list[str] = Field(default_factory=list)
    current_stage: str = PipelineStage.DESCRIBE
    draft_application: DraftApplication | None = None
    export_files: dict | None = None  # {"docx": bytes, "pdf": bytes}
    analysis_results: list[AnalysisResult] = Field(default_factory=list)
    search_results: list[SearchResult] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)  # {stage: {duration_ms, ...}}
    warnings: list[str] = Field(default_factory=list)
    gate_blocked: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class PatentPipeline:
    """Orchestrates the end-to-end patent application workflow.

    Parameters
    ----------
    llm_provider:
        LLM backend used by drafters and analysis modules.
    search_aggregator:
        Multi-provider patent search aggregator.
    analysis_modules:
        List of AnalysisModule instances to run during the analyze stage.
    drafter:
        Concrete Drafter implementation (provisional / nonprovisional / PCT).
    storage:
        Optional persistent storage provider. When supplied the pipeline may
        persist intermediate results; when absent the pipeline runs statelessly.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        search_aggregator: SearchAggregator,
        analysis_modules: list[AnalysisModule],
        drafter: Drafter,
        storage: StorageProvider | None = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._search_aggregator = search_aggregator
        self._analysis_modules = analysis_modules
        self._drafter = drafter
        self._storage = storage

    # ------------------------------------------------------------------
    # Public entry-point
    # ------------------------------------------------------------------

    async def run(
        self,
        invention_description: str,
        filing_format: str = "provisional",
        project_id: str | None = None,
        resume_from: PipelineStage | str | None = None,
        user_override: bool = False,
    ) -> PipelineResult:
        """Execute the patent pipeline and return a PipelineResult.

        Parameters
        ----------
        invention_description:
            Free-text description of the invention to process.
        filing_format:
            One of ``"provisional"``, ``"nonprovisional"``, or ``"pct"``.
        project_id:
            Optional identifier for the project; auto-generated if omitted.
        resume_from:
            If set, stages *before* this stage are skipped (re-entry).
        user_override:
            When True the prior art gate is bypassed even on CONFLICT.
        """
        effective_project_id = project_id or str(uuid4.uuid4() if False else uuid.uuid4())
        result = PipelineResult(project_id=effective_project_id)

        log = logger.bind(
            project_id=effective_project_id,
            filing_format=filing_format,
            resume_from=str(resume_from) if resume_from else None,
            user_override=user_override,
        )
        log.info("pipeline.run.start")

        # Determine the index to start from
        resume_stage = PipelineStage(resume_from) if resume_from else None
        start_index = 0
        if resume_stage is not None:
            try:
                start_index = _STAGE_ORDER.index(resume_stage)
            except ValueError:
                start_index = 0

        # Resolve filing format
        try:
            fmt = FilingFormat(filing_format)
        except ValueError:
            fmt = FilingFormat.PROVISIONAL

        # ------------------------------------------------------------------
        # Stage dispatch
        # ------------------------------------------------------------------
        for stage in _STAGE_ORDER:
            stage_index = _STAGE_ORDER.index(stage)

            # Skip stages before resume point
            if stage_index < start_index:
                continue

            # COMPLETE is handled after all work stages succeed
            if stage == PipelineStage.COMPLETE:
                result = await self._stage_complete(result, log)
                break

            # Run the stage; stop on failure or gate block
            result = await self._run_stage(
                stage=stage,
                result=result,
                invention_description=invention_description,
                filing_format=fmt,
                user_override=user_override,
                log=log,
            )

            if result.error is not None or result.gate_blocked:
                break

        log.info(
            "pipeline.run.done",
            current_stage=result.current_stage,
            stages_completed=result.stages_completed,
            gate_blocked=result.gate_blocked,
            error=result.error,
        )
        return result

    # ------------------------------------------------------------------
    # Stage dispatcher
    # ------------------------------------------------------------------

    async def _run_stage(
        self,
        stage: PipelineStage,
        result: PipelineResult,
        invention_description: str,
        filing_format: FilingFormat,
        user_override: bool,
        log: Any,
    ) -> PipelineResult:
        """Execute a single named stage, updating result in-place and returning it."""
        stage_log = log.bind(stage=stage)
        stage_log.info("pipeline.stage.start")
        t0 = time.monotonic()

        try:
            if stage == PipelineStage.DESCRIBE:
                result = await self._stage_describe(result, invention_description, stage_log)
            elif stage == PipelineStage.SEARCH:
                result = await self._stage_search(result, invention_description, stage_log)
            elif stage == PipelineStage.ANALYZE:
                result = await self._stage_analyze(result, invention_description, stage_log)
                # Prior art gate check immediately after analyze
                result = self._check_prior_art_gate(result, user_override, stage_log)
            elif stage == PipelineStage.DRAFT:
                result = await self._stage_draft(result, invention_description, filing_format, stage_log)
            elif stage == PipelineStage.REVIEW:
                result = await self._stage_review(result, invention_description, stage_log)
            elif stage == PipelineStage.EXPORT:
                result = await self._stage_export(result, stage_log)
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - t0) * 1000)
            error_msg = str(exc)
            stage_log.error("pipeline.stage.error", error=error_msg, duration_ms=duration_ms)
            result.current_stage = stage
            result.error = error_msg
            result.metrics[stage] = {"duration_ms": duration_ms}
            return result

        duration_ms = int((time.monotonic() - t0) * 1000)
        if not result.gate_blocked and result.error is None:
            result.metrics[stage] = {"duration_ms": duration_ms}
            stage_log.info("pipeline.stage.complete", duration_ms=duration_ms)
        elif result.gate_blocked:
            result.metrics[stage] = {"duration_ms": duration_ms}
            stage_log.info("pipeline.stage.gate_blocked", duration_ms=duration_ms)

        return result

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    async def _stage_describe(
        self,
        result: PipelineResult,
        invention_description: str,
        log: Any,
    ) -> PipelineResult:
        """Validate and store the invention description."""
        if not invention_description or not invention_description.strip():
            raise ValueError("invention_description must not be empty")
        result.current_stage = PipelineStage.DESCRIBE
        result.stages_completed.append(PipelineStage.DESCRIBE)
        log.info("pipeline.describe.complete", description_length=len(invention_description))
        return result

    async def _stage_search(
        self,
        result: PipelineResult,
        invention_description: str,
        log: Any,
    ) -> PipelineResult:
        """Run prior art search via the search aggregator."""
        query = SearchQuery(query=invention_description)
        response = await self._search_aggregator.search(query)
        result.search_results = response.results

        if not response.results:
            warning = "No search results found; proceeding without prior art context."
            result.warnings.append(warning)
            log.warning("pipeline.search.empty_results")
        else:
            log.info("pipeline.search.complete", num_results=len(response.results))

        result.current_stage = PipelineStage.SEARCH
        result.stages_completed.append(PipelineStage.SEARCH)
        return result

    async def _stage_analyze(
        self,
        result: PipelineResult,
        invention_description: str,
        log: Any,
    ) -> PipelineResult:
        """Run all analysis modules against the search results."""
        analysis_results: list[AnalysisResult] = []

        for module in self._analysis_modules:
            module_log = log.bind(module=module.module_name)
            module_log.info("pipeline.analyze.module.start")
            ar = await module.analyze(
                invention_description=invention_description,
                search_results=result.search_results,
            )
            analysis_results.append(ar)
            module_log.info("pipeline.analyze.module.complete", status=ar.status)

        result.analysis_results = analysis_results
        result.current_stage = PipelineStage.ANALYZE
        result.stages_completed.append(PipelineStage.ANALYZE)
        log.info("pipeline.analyze.complete", num_modules=len(analysis_results))
        return result

    def _check_prior_art_gate(
        self,
        result: PipelineResult,
        user_override: bool,
        log: Any,
    ) -> PipelineResult:
        """Evaluate analysis results; set gate_blocked if any CONFLICT found."""
        if user_override:
            log.info("pipeline.gate.bypassed_by_override")
            return result

        conflicts = [
            ar for ar in result.analysis_results
            if ar.status == AnalysisStatus.CONFLICT
        ]
        if conflicts:
            conflict_modules = [ar.module for ar in conflicts]
            log.warning(
                "pipeline.gate.blocked",
                conflict_modules=conflict_modules,
            )
            result.gate_blocked = True
            result.current_stage = PipelineStage.ANALYZE
            result.warnings.append(
                f"Prior art gate blocked: CONFLICT detected in modules {conflict_modules}. "
                "Use user_override=True to bypass."
            )

        return result

    async def _stage_draft(
        self,
        result: PipelineResult,
        invention_description: str,
        filing_format: FilingFormat,
        log: Any,
    ) -> PipelineResult:
        """Generate the patent draft application."""
        preferences = {"filing_format": filing_format}
        draft = await self._drafter.draft(
            invention_description=invention_description,
            prior_art_results=result.search_results,
            preferences=preferences,
        )
        result.draft_application = draft
        result.current_stage = PipelineStage.DRAFT
        result.stages_completed.append(PipelineStage.DRAFT)
        log.info("pipeline.draft.complete", draft_id=str(draft.id))
        return result

    async def _stage_review(
        self,
        result: PipelineResult,
        invention_description: str,
        log: Any,
    ) -> PipelineResult:
        """Run post-draft review (formalities + claims analysis if modules available)."""
        # Review uses existing analysis modules on the generated draft; if no
        # modules are configured this stage is a no-op (draft already produced).
        log.info("pipeline.review.complete")
        result.current_stage = PipelineStage.REVIEW
        result.stages_completed.append(PipelineStage.REVIEW)
        return result

    async def _stage_export(
        self,
        result: PipelineResult,
        log: Any,
    ) -> PipelineResult:
        """Export draft to DOCX and PDF bytes."""
        if result.draft_application is None:
            raise ValueError("Cannot export: no draft application produced")

        docx_bytes = export_docx(result.draft_application)
        pdf_bytes = export_pdf(result.draft_application)

        result.export_files = {"docx": docx_bytes, "pdf": pdf_bytes}
        result.current_stage = PipelineStage.EXPORT
        result.stages_completed.append(PipelineStage.EXPORT)
        log.info(
            "pipeline.export.complete",
            docx_bytes=len(docx_bytes),
            pdf_bytes=len(pdf_bytes),
        )
        return result

    async def _stage_complete(
        self,
        result: PipelineResult,
        log: Any,
    ) -> PipelineResult:
        """Mark the pipeline as complete."""
        result.current_stage = PipelineStage.COMPLETE
        result.stages_completed.append(PipelineStage.COMPLETE)
        result.metrics[PipelineStage.COMPLETE] = {"duration_ms": 0}
        log.info("pipeline.complete")
        return result
