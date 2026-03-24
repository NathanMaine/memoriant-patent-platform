from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from core.models.patent import Claim


class FilingFormat(StrEnum):
    PROVISIONAL = "provisional"
    NONPROVISIONAL = "nonprovisional"
    PCT = "pct"


class ReviewType(StrEnum):
    ELIGIBILITY_101 = "101"
    NOVELTY_102 = "102"
    OBVIOUSNESS_103 = "103"
    WRITTEN_DESCRIPTION_112A = "112a"
    INDEFINITENESS_112B = "112b"
    FORMALITIES = "formalities"


class ReviewSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Embodiment(BaseModel):
    title: str
    description: str


class Specification(BaseModel):
    background: str
    summary: str
    detailed_description: str
    embodiments: list[Embodiment] = Field(default_factory=list)


class ReviewNote(BaseModel):
    type: ReviewType
    finding: str
    severity: ReviewSeverity
    suggestion: str


class DraftApplication(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    version: int = 1
    filing_format: FilingFormat
    title: str
    abstract: str | None = None
    specification: Specification
    claims: list[Claim] = Field(default_factory=list)
    drawings_description: str | None = None
    ads_data: dict | None = None
    review_notes: list[ReviewNote] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("abstract")
    @classmethod
    def validate_abstract_length(cls, v: str | None) -> str | None:
        if v is not None and len(v.split()) > 150:
            raise ValueError("Abstract must be 150 words or fewer per USPTO rules")
        return v
