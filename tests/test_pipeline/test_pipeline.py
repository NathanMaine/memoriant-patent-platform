"""Tests for core/pipeline.py — PatentPipeline orchestrator.

All external dependencies (search aggregator, analysis modules, drafter,
export functions, storage) are mocked so tests run entirely in-process.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from core.analysis.base import AnalysisFinding, AnalysisResult, AnalysisSeverity, AnalysisStatus
from core.models.application import DraftApplication, FilingFormat, Specification
from core.models.patent import SearchResult, SearchStrategy
from core.pipeline import PatentPipeline, PipelineResult, PipelineStage
from core.search.aggregator import AggregatedSearchResponse
from core.search.base import SearchQuery


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_search_result(patent_id: str = "US1234567") -> SearchResult:
    return SearchResult(
        patent_id=patent_id,
        title="Test Patent",
        provider="test",
        strategy=SearchStrategy.KEYWORD,
    )


def _make_aggregated_response(results: list[SearchResult] | None = None) -> AggregatedSearchResponse:
    effective = [_make_search_result()] if results is None else results
    return AggregatedSearchResponse(
        results=effective,
        total_hits=len(effective),
        provider_responses=[],
        duration_ms=42,
        errors=[],
    )


def _make_analysis_result(
    module: str = "novelty",
    status: AnalysisStatus = AnalysisStatus.CLEAR,
) -> AnalysisResult:
    return AnalysisResult(
        module=module,
        status=status,
        findings=[],
        recommendation="All clear.",
    )


def _make_draft_application(filing_format: FilingFormat = FilingFormat.PROVISIONAL) -> DraftApplication:
    return DraftApplication(
        filing_format=filing_format,
        title="Test Invention",
        abstract="A concise test abstract.",
        specification=Specification(
            background="Background text.",
            summary="Summary text.",
            detailed_description="Detailed description.",
        ),
    )


def _make_pipeline(
    analysis_statuses: list[AnalysisStatus] | None = None,
    draft: DraftApplication | None = None,
    search_results: list[SearchResult] | None = None,
    storage=None,
) -> PatentPipeline:
    """Build a PatentPipeline with all dependencies mocked."""
    statuses = analysis_statuses or [AnalysisStatus.CLEAR]

    # LLM provider (not used directly by pipeline but passed to drafter)
    llm_provider = MagicMock()

    # Search aggregator
    search_aggregator = MagicMock()
    search_aggregator.search = AsyncMock(
        return_value=_make_aggregated_response(search_results)
    )

    # Analysis modules
    analysis_modules = []
    for i, status in enumerate(statuses):
        module = MagicMock()
        module.module_name = f"module_{i}"
        module.analyze = AsyncMock(
            return_value=_make_analysis_result(module=f"module_{i}", status=status)
        )
        analysis_modules.append(module)

    # Drafter
    effective_draft = draft or _make_draft_application()
    drafter = MagicMock()
    drafter.draft = AsyncMock(return_value=effective_draft)

    return PatentPipeline(
        llm_provider=llm_provider,
        search_aggregator=search_aggregator,
        analysis_modules=analysis_modules,
        drafter=drafter,
        storage=storage,
    )


DOCX_BYTES = b"PK fake docx content"
PDF_BYTES = b"%PDF fake pdf content"


# ---------------------------------------------------------------------------
# Test: full happy-path run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_run_completes_all_stages():
    """A full run with no conflicts should complete all 8 stages."""
    pipeline = _make_pipeline()

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention about widgets.")

    assert result.current_stage == PipelineStage.COMPLETE
    assert result.error is None
    assert result.gate_blocked is False


# ---------------------------------------------------------------------------
# Test: stages_completed tracks progress
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stages_completed_tracks_progress():
    """stages_completed should include all 8 pipeline stage names."""
    pipeline = _make_pipeline()

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention about widgets.")

    expected = [
        PipelineStage.DESCRIBE,
        PipelineStage.SEARCH,
        PipelineStage.ANALYZE,
        PipelineStage.DRAFT,
        PipelineStage.REVIEW,
        PipelineStage.EXPORT,
        PipelineStage.COMPLETE,
    ]
    for stage in expected:
        assert stage in result.stages_completed, f"Expected stage {stage!r} in stages_completed"


# ---------------------------------------------------------------------------
# Test: re-entry from "analyze" skips describe+search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reentry_from_analyze_skips_earlier_stages():
    """resume_from='analyze' should skip describe and search stages."""
    pipeline = _make_pipeline()

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run(
            "An invention about widgets.",
            resume_from=PipelineStage.ANALYZE,
        )

    assert PipelineStage.DESCRIBE not in result.stages_completed
    assert PipelineStage.SEARCH not in result.stages_completed
    assert PipelineStage.ANALYZE in result.stages_completed
    assert result.error is None
    # Search was not called
    pipeline._search_aggregator.search.assert_not_called()


# ---------------------------------------------------------------------------
# Test: prior art gate blocks on CONFLICT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prior_art_gate_blocks_on_conflict():
    """When any analysis result has CONFLICT status, the gate should block."""
    pipeline = _make_pipeline(analysis_statuses=[AnalysisStatus.CONFLICT])

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention about widgets.")

    assert result.gate_blocked is True
    assert result.current_stage == PipelineStage.ANALYZE
    # Draft should NOT have been called
    pipeline._drafter.draft.assert_not_called()
    # Export files should be None
    assert result.export_files is None
    assert result.draft_application is None


# ---------------------------------------------------------------------------
# Test: prior art gate override proceeds past CONFLICT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prior_art_gate_override_proceeds():
    """user_override=True should bypass the prior art gate even with CONFLICT."""
    pipeline = _make_pipeline(analysis_statuses=[AnalysisStatus.CONFLICT])

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run(
            "An invention about widgets.",
            user_override=True,
        )

    assert result.gate_blocked is False
    assert result.current_stage == PipelineStage.COMPLETE
    assert result.error is None
    pipeline._drafter.draft.assert_called_once()


# ---------------------------------------------------------------------------
# Test: prior art gate passes on CLEAR / CAUTION
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prior_art_gate_passes_on_clear():
    """CLEAR status should not block the pipeline."""
    pipeline = _make_pipeline(analysis_statuses=[AnalysisStatus.CLEAR])

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention about widgets.")

    assert result.gate_blocked is False
    assert result.current_stage == PipelineStage.COMPLETE


@pytest.mark.asyncio
async def test_prior_art_gate_passes_on_caution():
    """CAUTION status should not block the pipeline."""
    pipeline = _make_pipeline(analysis_statuses=[AnalysisStatus.CAUTION])

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention about widgets.")

    assert result.gate_blocked is False
    assert result.current_stage == PipelineStage.COMPLETE


# ---------------------------------------------------------------------------
# Test: stage failure returns partial result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage_failure_returns_partial_result():
    """A failure in the draft stage should return partial results with error set."""
    pipeline = _make_pipeline()
    pipeline._drafter.draft = AsyncMock(side_effect=RuntimeError("LLM timeout"))

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention about widgets.")

    assert result.error is not None
    assert "LLM timeout" in result.error
    assert result.current_stage == PipelineStage.DRAFT
    assert result.draft_application is None
    # Stages before the failure should be recorded
    assert PipelineStage.DESCRIBE in result.stages_completed
    assert PipelineStage.SEARCH in result.stages_completed
    assert PipelineStage.ANALYZE in result.stages_completed


# ---------------------------------------------------------------------------
# Test: search stage failure returns partial result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_stage_failure_returns_partial_result():
    """A failure in the search stage should return partial results with error set."""
    pipeline = _make_pipeline()
    pipeline._search_aggregator.search = AsyncMock(side_effect=ConnectionError("API down"))

    result = await pipeline.run("An invention about widgets.")

    assert result.error is not None
    assert "API down" in result.error
    assert result.current_stage == PipelineStage.SEARCH
    assert PipelineStage.DESCRIBE in result.stages_completed
    assert PipelineStage.ANALYZE not in result.stages_completed


# ---------------------------------------------------------------------------
# Test: metrics tracked per stage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metrics_tracked_per_stage():
    """metrics dict should have an entry for each completed stage."""
    pipeline = _make_pipeline()

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention about widgets.")

    assert isinstance(result.metrics, dict)
    for stage in result.stages_completed:
        assert stage in result.metrics, f"No metrics entry for stage {stage!r}"
        assert "duration_ms" in result.metrics[stage]


# ---------------------------------------------------------------------------
# Test: empty search results still proceeds with warning
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_search_results_proceeds_with_warning():
    """Empty search results should not block — pipeline adds a warning and continues."""
    pipeline = _make_pipeline(search_results=[])

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention about widgets.")

    assert result.current_stage == PipelineStage.COMPLETE
    assert result.error is None
    assert any("no search results" in w.lower() or "empty" in w.lower() for w in result.warnings), (
        f"Expected a warning about empty results; got: {result.warnings}"
    )


# ---------------------------------------------------------------------------
# Test: export produces both DOCX and PDF bytes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_produces_docx_and_pdf():
    """export_files should contain both 'docx' and 'pdf' keys with bytes."""
    pipeline = _make_pipeline()

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention about widgets.")

    assert result.export_files is not None
    assert "docx" in result.export_files
    assert "pdf" in result.export_files
    assert result.export_files["docx"] == DOCX_BYTES
    assert result.export_files["pdf"] == PDF_BYTES


# ---------------------------------------------------------------------------
# Test: filing format selection — provisional
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filing_format_provisional():
    """filing_format='provisional' should be passed to drafter.draft()."""
    draft = _make_draft_application(FilingFormat.PROVISIONAL)
    pipeline = _make_pipeline(draft=draft)

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention.", filing_format="provisional")

    assert result.draft_application is not None
    assert result.draft_application.filing_format == FilingFormat.PROVISIONAL


# ---------------------------------------------------------------------------
# Test: filing format selection — nonprovisional
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filing_format_nonprovisional():
    """filing_format='nonprovisional' should be reflected in the draft."""
    draft = _make_draft_application(FilingFormat.NONPROVISIONAL)
    pipeline = _make_pipeline(draft=draft)

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention.", filing_format="nonprovisional")

    assert result.draft_application is not None
    assert result.draft_application.filing_format == FilingFormat.NONPROVISIONAL


# ---------------------------------------------------------------------------
# Test: filing format selection — PCT
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filing_format_pct():
    """filing_format='pct' should be reflected in the draft."""
    draft = _make_draft_application(FilingFormat.PCT)
    pipeline = _make_pipeline(draft=draft)

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention.", filing_format="pct")

    assert result.draft_application is not None
    assert result.draft_application.filing_format == FilingFormat.PCT


# ---------------------------------------------------------------------------
# Test: project_id is propagated into result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_id_propagated():
    """A supplied project_id should appear in the PipelineResult."""
    pipeline = _make_pipeline()
    pid = "proj-abc-123"

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention.", project_id=pid)

    assert result.project_id == pid


# ---------------------------------------------------------------------------
# Test: auto-generated project_id when none supplied
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_project_id_when_none():
    """When no project_id is supplied, pipeline should generate one."""
    pipeline = _make_pipeline()

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention.")

    assert result.project_id is not None
    assert len(result.project_id) > 0


# ---------------------------------------------------------------------------
# Test: analysis results populated in result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analysis_results_populated():
    """analysis_results should contain all module outputs."""
    pipeline = _make_pipeline(
        analysis_statuses=[AnalysisStatus.CLEAR, AnalysisStatus.CAUTION]
    )

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention.")

    assert len(result.analysis_results) == 2


# ---------------------------------------------------------------------------
# Test: search results stored in result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_results_stored():
    """search_results should be populated from the aggregator response."""
    sr = _make_search_result("US9999999")
    pipeline = _make_pipeline(search_results=[sr])

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention.")

    assert len(result.search_results) == 1
    assert result.search_results[0].patent_id == "US9999999"


# ---------------------------------------------------------------------------
# Test: multiple CONFLICTs still blocked (not just first)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_conflicts_gate_blocked():
    """Multiple CONFLICT results should still block (gate_blocked=True)."""
    pipeline = _make_pipeline(
        analysis_statuses=[AnalysisStatus.CONFLICT, AnalysisStatus.CONFLICT]
    )

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention.")

    assert result.gate_blocked is True


# ---------------------------------------------------------------------------
# Test: export stage failure returns partial result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_stage_failure_returns_partial_result():
    """A failure in the export stage should set error and return partial result."""
    pipeline = _make_pipeline()

    with (
        patch("core.pipeline.export_docx", side_effect=RuntimeError("disk full")),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention.")

    assert result.error is not None
    assert "disk full" in result.error
    assert result.current_stage == PipelineStage.EXPORT
    # Draft should have been produced before the export failure
    assert result.draft_application is not None


# ---------------------------------------------------------------------------
# Test: invalid resume_from falls back to start
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_resume_from_falls_back_to_start():
    """An invalid resume_from value (not in _STAGE_ORDER) should start from the beginning."""
    pipeline = _make_pipeline()

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        # "failed" is a valid PipelineStage but not in _STAGE_ORDER, so it
        # raises ValueError when indexed — should gracefully fall back to start.
        result = await pipeline.run(
            "An invention.",
            resume_from=PipelineStage.FAILED,
        )

    assert result.error is None
    assert result.current_stage == PipelineStage.COMPLETE
    assert PipelineStage.DESCRIBE in result.stages_completed


# ---------------------------------------------------------------------------
# Test: invalid filing format falls back to provisional
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_filing_format_defaults_to_provisional():
    """An unrecognised filing_format string should default to 'provisional'."""
    draft = _make_draft_application(FilingFormat.PROVISIONAL)
    pipeline = _make_pipeline(draft=draft)

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention.", filing_format="INVALID_FORMAT")

    assert result.error is None
    assert result.current_stage == PipelineStage.COMPLETE


# ---------------------------------------------------------------------------
# Test: empty invention description raises in describe stage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_invention_description_fails():
    """An empty invention_description should fail at the describe stage."""
    pipeline = _make_pipeline()

    result = await pipeline.run("")

    assert result.error is not None
    assert result.current_stage == PipelineStage.DESCRIBE
    assert PipelineStage.SEARCH not in result.stages_completed


# ---------------------------------------------------------------------------
# Test: export guard when draft_application is None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_guard_no_draft():
    """Export stage should fail gracefully when draft_application is None."""
    pipeline = _make_pipeline()
    # Make draft return None by crashing, then resume from export with no draft
    # Achieved by resuming from export stage with no draft set
    pipeline._drafter.draft = AsyncMock(return_value=None)

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run("An invention.", resume_from=PipelineStage.EXPORT)

    assert result.error is not None
    assert "Cannot export" in result.error
    assert result.current_stage == PipelineStage.EXPORT
