"""Tests for API request/response schemas (Task 5)."""
import pytest
from pydantic import ValidationError

from api.schemas.requests import (
    AnalyzeRequest,
    ConfigUpdateRequest,
    DraftRequest,
    PipelineRequest,
    SearchRequest,
)
from api.schemas.responses import (
    AnalyzeResponse,
    ConfigUpdateResponse,
    DraftResponse,
    HealthResponse,
    PipelineResponse,
    SearchResponse,
)


# ---------------------------------------------------------------------------
# SearchRequest
# ---------------------------------------------------------------------------

class TestSearchRequest:
    def test_minimal_valid(self):
        req = SearchRequest(query="autonomous vehicle battery")
        assert req.query == "autonomous vehicle battery"
        assert req.project_id is None
        assert req.strategies == ["keyword"]
        assert req.providers == ["patentsview", "uspto_odp"]
        assert req.date_range is None
        assert req.cpc_codes == []
        assert req.max_results == 50

    def test_full_valid(self):
        req = SearchRequest(
            project_id="proj-123",
            query="neural network",
            strategies=["keyword", "semantic"],
            providers=["patentsview"],
            date_range={"start": "2020-01-01", "end": "2024-01-01"},
            cpc_codes=["G06N3/04"],
            max_results=100,
        )
        assert req.project_id == "proj-123"
        assert req.cpc_codes == ["G06N3/04"]
        assert req.max_results == 100

    def test_missing_query_raises(self):
        with pytest.raises(ValidationError):
            SearchRequest()

    def test_defaults_are_independent_instances(self):
        """Mutable defaults must not be shared across instances."""
        a = SearchRequest(query="foo")
        b = SearchRequest(query="bar")
        a.strategies.append("semantic")
        assert "semantic" not in b.strategies


# ---------------------------------------------------------------------------
# AnalyzeRequest
# ---------------------------------------------------------------------------

class TestAnalyzeRequest:
    def test_minimal_valid(self):
        req = AnalyzeRequest(
            project_id="proj-abc",
            invention_description="A method for...",
        )
        assert req.project_id == "proj-abc"
        assert req.search_result_ids == []
        assert req.checks == [
            "novelty",
            "obviousness",
            "eligibility",
            "claims",
            "specification",
            "formalities",
        ]

    def test_full_valid(self):
        req = AnalyzeRequest(
            project_id="proj-abc",
            invention_description="A method for...",
            search_result_ids=["sr-1", "sr-2"],
            checks=["novelty", "obviousness"],
        )
        assert req.search_result_ids == ["sr-1", "sr-2"]
        assert req.checks == ["novelty", "obviousness"]

    def test_missing_required_fields_raise(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(invention_description="desc")

        with pytest.raises(ValidationError):
            AnalyzeRequest(project_id="proj-abc")

    def test_defaults_are_independent_instances(self):
        a = AnalyzeRequest(project_id="p1", invention_description="d")
        b = AnalyzeRequest(project_id="p2", invention_description="d")
        a.search_result_ids.append("x")
        assert "x" not in b.search_result_ids


# ---------------------------------------------------------------------------
# DraftRequest
# ---------------------------------------------------------------------------

class TestDraftRequest:
    def test_minimal_valid(self):
        req = DraftRequest(
            project_id="proj-xyz",
            invention_description="A widget that...",
        )
        assert req.filing_format == "provisional"
        assert req.prior_art_analysis_id is None
        assert req.preferences == {}

    def test_full_valid(self):
        req = DraftRequest(
            project_id="proj-xyz",
            filing_format="nonprovisional",
            invention_description="A widget that...",
            prior_art_analysis_id="analysis-1",
            preferences={"claim_count": 20},
        )
        assert req.filing_format == "nonprovisional"
        assert req.prior_art_analysis_id == "analysis-1"
        assert req.preferences == {"claim_count": 20}

    def test_missing_required_fields_raise(self):
        with pytest.raises(ValidationError):
            DraftRequest(project_id="p")  # missing invention_description

        with pytest.raises(ValidationError):
            DraftRequest(invention_description="desc")  # missing project_id


# ---------------------------------------------------------------------------
# PipelineRequest
# ---------------------------------------------------------------------------

class TestPipelineRequest:
    def test_minimal_valid(self):
        req = PipelineRequest(invention_description="A new type of battery.")
        assert req.project_id is None
        assert req.filing_format == "provisional"
        assert req.resume_from is None
        assert req.user_override is False

    def test_full_valid(self):
        req = PipelineRequest(
            project_id="proj-1",
            invention_description="desc",
            filing_format="nonprovisional",
            resume_from="analyze",
            user_override=True,
        )
        assert req.project_id == "proj-1"
        assert req.resume_from == "analyze"
        assert req.user_override is True

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            PipelineRequest()


# ---------------------------------------------------------------------------
# ConfigUpdateRequest
# ---------------------------------------------------------------------------

class TestConfigUpdateRequest:
    def test_all_optional(self):
        req = ConfigUpdateRequest()
        assert req.llm_provider is None
        assert req.llm_model is None
        assert req.llm_endpoint is None
        assert req.patentsview_api_key is None
        assert req.serpapi_key is None

    def test_partial(self):
        req = ConfigUpdateRequest(llm_provider="openai", llm_model="gpt-4o")
        assert req.llm_provider == "openai"
        assert req.llm_model == "gpt-4o"
        assert req.serpapi_key is None

    def test_full(self):
        req = ConfigUpdateRequest(
            llm_provider="openai",
            llm_model="gpt-4o",
            llm_endpoint="http://localhost:1234/v1",
            patentsview_api_key="pv-key",
            serpapi_key="serp-key",
        )
        assert req.patentsview_api_key == "pv-key"
        assert req.serpapi_key == "serp-key"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TestHealthResponse:
    def test_valid(self):
        r = HealthResponse(status="healthy", version="0.1.0")
        assert r.status == "healthy"
        assert r.version == "0.1.0"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            HealthResponse(status="healthy")


class TestSearchResponse:
    def test_valid_empty_results(self):
        r = SearchResponse(
            project_id="p1",
            query="foo",
            results=[],
            total=0,
            strategies_used=["keyword"],
        )
        assert r.total == 0
        assert r.results == []

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            SearchResponse(query="foo", results=[], total=0, strategies_used=[])


class TestAnalyzeResponse:
    def test_valid(self):
        r = AnalyzeResponse(
            project_id="p1",
            analysis_id="a1",
            checks_completed=["novelty"],
            summary="Looks novel.",
        )
        assert r.analysis_id == "a1"
        assert r.checks_completed == ["novelty"]

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            AnalyzeResponse(project_id="p1", analysis_id="a1")


class TestDraftResponse:
    def test_valid(self):
        r = DraftResponse(
            project_id="p1",
            draft_id="d1",
            filing_format="provisional",
            sections=["abstract", "claims"],
        )
        assert r.draft_id == "d1"
        assert r.sections == ["abstract", "claims"]

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            DraftResponse(project_id="p1", draft_id="d1")


class TestPipelineResponse:
    def test_valid(self):
        r = PipelineResponse(
            project_id="p1",
            pipeline_id="pip-1",
            status="completed",
            stages_completed=["search", "analyze", "draft"],
        )
        assert r.status == "completed"
        assert "search" in r.stages_completed

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            PipelineResponse(project_id="p1", pipeline_id="pip-1")


class TestConfigUpdateResponse:
    def test_valid(self):
        r = ConfigUpdateResponse(updated_fields=["llm_provider"], message="Config updated.")
        assert r.updated_fields == ["llm_provider"]
        assert r.message == "Config updated."

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            ConfigUpdateResponse(message="ok")
