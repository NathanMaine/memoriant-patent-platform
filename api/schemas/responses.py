"""API response schemas for all platform endpoints."""
from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict = {}


class SearchResponse(BaseModel):
    project_id: str
    query: str
    results: list[dict]
    total: int
    strategies_used: list[str]


class AnalyzeResponse(BaseModel):
    project_id: str
    analysis_id: str
    checks_completed: list[str]
    summary: str


class DraftResponse(BaseModel):
    project_id: str
    draft_id: str
    filing_format: str
    sections: list[str]


class PipelineResponse(BaseModel):
    project_id: str
    pipeline_id: str
    status: str
    stages_completed: list[str]


class ConfigUpdateResponse(BaseModel):
    updated_fields: list[str]
    message: str
