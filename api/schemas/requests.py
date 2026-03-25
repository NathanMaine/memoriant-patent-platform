"""API request schemas (Appendix E of the patent platform spec)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    project_id: str | None = None
    query: str
    strategies: list[str] = Field(default_factory=lambda: ["keyword"])
    providers: list[str] = Field(default_factory=lambda: ["patentsview", "uspto_odp"])
    date_range: dict | None = None
    cpc_codes: list[str] = Field(default_factory=list)
    max_results: int = 50


class AnalyzeRequest(BaseModel):
    project_id: str
    invention_description: str
    search_result_ids: list[str] = Field(default_factory=list)
    checks: list[str] = Field(
        default_factory=lambda: [
            "novelty",
            "obviousness",
            "eligibility",
            "claims",
            "specification",
            "formalities",
        ]
    )


class DraftRequest(BaseModel):
    project_id: str
    filing_format: str = "provisional"
    invention_description: str
    prior_art_analysis_id: str | None = None
    preferences: dict = Field(default_factory=dict)


class PipelineRequest(BaseModel):
    project_id: str | None = None
    invention_description: str
    filing_format: str = "provisional"
    resume_from: str | None = None
    user_override: bool = False


class ConfigUpdateRequest(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_endpoint: str | None = None
    patentsview_api_key: str | None = None
    serpapi_key: str | None = None
