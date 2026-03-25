"""Draft route — POST /draft."""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends

from api.deps import get_drafter, get_user_id
from api.schemas.requests import DraftRequest
from api.schemas.responses import DraftResponse

logger = structlog.get_logger(__name__)

router = APIRouter()

# Map filing_format → section names present in a draft
_FORMAT_SECTIONS: dict[str, list[str]] = {
    "provisional": ["title", "abstract", "background", "summary", "detailed_description"],
    "nonprovisional": [
        "title", "abstract", "background", "summary",
        "detailed_description", "claims", "drawings",
    ],
    "pct": [
        "title", "abstract", "background", "summary",
        "detailed_description", "claims", "drawings", "international_search_report",
    ],
}


@router.post("/draft", response_model=DraftResponse, tags=["draft"])
async def draft(
    request: DraftRequest,
    user_id: str = Depends(get_user_id),
    drafter=Depends(get_drafter),
) -> DraftResponse:
    """Generate a patent application draft for the specified filing format."""
    log = logger.bind(
        user_id=user_id,
        project_id=request.project_id,
        filing_format=request.filing_format,
    )
    log.info("draft.start")

    application = await drafter.draft(
        invention_description=request.invention_description,
        prior_art_results=None,
        preferences=request.preferences,
    )

    draft_id = str(application.id)
    sections = _FORMAT_SECTIONS.get(request.filing_format, ["title", "abstract", "specification"])
    log.info("draft.complete", draft_id=draft_id)

    return DraftResponse(
        project_id=request.project_id,
        draft_id=draft_id,
        filing_format=request.filing_format,
        sections=sections,
    )
