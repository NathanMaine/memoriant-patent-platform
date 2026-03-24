from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PatentType(StrEnum):
    UTILITY = "utility"
    DESIGN = "design"
    PLANT = "plant"
    REISSUE = "reissue"


class SearchStrategy(StrEnum):
    KEYWORD = "keyword"
    CLASSIFICATION = "classification"
    CITATION = "citation"
    ASSIGNEE = "assignee"
    INVENTOR = "inventor"
    DATE_RANGE = "date_range"
    BOOLEAN = "boolean"


class Inventor(BaseModel):
    first: str
    last: str
    city: str | None = None
    state: str | None = None
    country: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"


class Assignee(BaseModel):
    organization: str | None = None
    first: str | None = None
    last: str | None = None


class Citation(BaseModel):
    patent_id: str
    direction: str = "backward"


class Claim(BaseModel):
    number: int
    type: str
    text: str
    depends_on: int | None = None

    @model_validator(mode="after")
    def validate_dependent_claim(self):
        if self.type == "dependent" and self.depends_on is None:
            raise ValueError("Dependent claims must specify depends_on")
        return self


class SearchResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    patent_id: str
    title: str
    abstract: str | None = None
    patent_date: date | None = None
    patent_type: PatentType | None = None
    inventors: list[Inventor] = Field(default_factory=list)
    assignees: list[Assignee] = Field(default_factory=list)
    cpc_codes: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    relevance_score: float | None = None
    relevance_notes: str | None = None
    provider: str
    strategy: SearchStrategy


class Patent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    patent_id: str
    title: str
    abstract: str | None = None
    patent_date: date | None = None
    patent_type: PatentType = PatentType.UTILITY
    inventors: list[Inventor] = Field(default_factory=list)
    assignees: list[Assignee] = Field(default_factory=list)
    cpc_codes: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    num_claims: int | None = None
