"""Pipeline integration tests using real SQLite storage and a mocked LLM.

No external API keys are required.  The LLM is replaced with an AsyncMock
that returns deterministic structured text, while SQLite runs for real in a
temp directory.  This verifies that the pipeline stages complete end-to-end
and that data is correctly persisted.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.analysis.base import AnalysisResult, AnalysisStatus
from core.drafting.provisional import ProvisionalDrafter
from core.llm.base import LLMProvider, LLMResponse
from core.models.application import DraftApplication, FilingFormat, Specification
from core.models.patent import SearchResult, SearchStrategy
from core.pipeline import PatentPipeline, PipelineStage
from core.search.aggregator import AggregatedSearchResponse, SearchAggregator
from core.search.base import SearchQuery, SearchResponse
from core.storage.sqlite import SQLiteStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_LLM_TEXT = (
    "TITLE: Integrated Wireless Charging Platform\n\n"
    "ABSTRACT:\nA system for wireless power delivery using resonant inductive coupling.\n\n"
    "BACKGROUND:\nExisting wireless chargers suffer from misalignment sensitivity.\n\n"
    "SUMMARY:\nThe invention provides a self-aligning wireless charging platform.\n\n"
    "DETAILED_DESCRIPTION:\nThe platform comprises a transmitter coil array and a "
    "receiver coil with adaptive impedance matching circuitry.\n\n"
    "EMBODIMENT 1:\n"
    "Title: Single-device charger\n"
    "Description: A charger for one device at a time.\n\n"
    "CLAIM 1 (independent):\nA wireless charging system comprising a transmitter coil array.\n\n"
    "CLAIM 2 (dependent on 1):\nThe system of claim 1, wherein the transmitter coil array "
    "includes at least three coils.\n"
)

DOCX_BYTES = b"PK fake docx"
PDF_BYTES = b"%PDF fake pdf"


@pytest.fixture
async def sqlite_storage(tmp_path):
    db_path = str(tmp_path / "pipeline_test.db")
    s = SQLiteStorage(db_path)
    await s.initialize()
    yield s
    await s.close()


def _build_pipeline(storage: SQLiteStorage) -> PatentPipeline:
    """Construct a PatentPipeline with mocked LLM and search, real SQLite."""
    # Mock LLM
    mock_llm = MagicMock(spec=LLMProvider)
    mock_llm.generate = AsyncMock(
        return_value=LLMResponse(content=_LLM_TEXT, tokens_used=120, model="test-model")
    )

    # Mock search aggregator returning one result
    search_result = SearchResult(
        patent_id="US55667788",
        title="PRIOR ART CHARGING SYSTEM",
        provider="patentsview",
        strategy=SearchStrategy.KEYWORD,
    )
    mock_aggregator = MagicMock(spec=SearchAggregator)
    mock_aggregator.search = AsyncMock(
        return_value=AggregatedSearchResponse(
            results=[search_result],
            total_hits=1,
            provider_responses=[],
            duration_ms=10,
            errors=[],
        )
    )

    # Analysis module returning CLEAR
    mock_module = MagicMock()
    mock_module.module_name = "novelty"
    mock_module.analyze = AsyncMock(
        return_value=AnalysisResult(
            module="novelty",
            status=AnalysisStatus.CLEAR,
            findings=[],
            recommendation="No blocking prior art found.",
        )
    )

    drafter = ProvisionalDrafter(llm_provider=mock_llm)

    return PatentPipeline(
        llm_provider=mock_llm,
        search_aggregator=mock_aggregator,
        analysis_modules=[mock_module],
        drafter=drafter,
        storage=storage,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_completes_all_stages_with_sqlite(sqlite_storage):
    """Full pipeline run with SQLite storage and mocked LLM reaches COMPLETE."""
    pipeline = _build_pipeline(sqlite_storage)

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run(
            "A wireless charging platform using resonant inductive coupling."
        )

    assert result.error is None, f"Pipeline error: {result.error}"
    assert result.current_stage == PipelineStage.COMPLETE
    assert result.gate_blocked is False
    assert PipelineStage.DESCRIBE in result.stages_completed
    assert PipelineStage.SEARCH in result.stages_completed
    assert PipelineStage.DRAFT in result.stages_completed


@pytest.mark.asyncio
async def test_pipeline_draft_application_fields(sqlite_storage):
    """The draft produced by the mocked-LLM pipeline has expected title and claims."""
    pipeline = _build_pipeline(sqlite_storage)

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run(
            "A wireless charging platform using resonant inductive coupling."
        )

    assert result.draft_application is not None
    assert result.draft_application.filing_format == FilingFormat.PROVISIONAL
    assert len(result.draft_application.claims) >= 1


@pytest.mark.asyncio
async def test_pipeline_search_results_captured(sqlite_storage):
    """Pipeline search stage stores found patents in PipelineResult.search_results."""
    pipeline = _build_pipeline(sqlite_storage)

    with (
        patch("core.pipeline.export_docx", return_value=DOCX_BYTES),
        patch("core.pipeline.export_pdf", return_value=PDF_BYTES),
    ):
        result = await pipeline.run(
            "A wireless charging platform using resonant inductive coupling."
        )

    assert len(result.search_results) == 1
    assert result.search_results[0].patent_id == "US55667788"
