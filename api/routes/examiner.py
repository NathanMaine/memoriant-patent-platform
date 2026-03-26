"""Examiner statistics route — GET /examiner/ endpoints."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_user_id
from core.analysis.examiner_stats import ExaminerStats, get_examiner_stats, lookup_examiner

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/examiner", tags=["examiner"])


@router.get("/art-unit/{art_unit}", response_model=list[ExaminerStats])
async def get_art_unit_examiners(
    art_unit: str,
    user_id: str = Depends(get_user_id),
) -> list[ExaminerStats]:
    """Return examiner statistics for all examiners in the given art unit.

    Uses the PatentsView API.  The PatentsView API key is read from the
    ``PATENTSVIEW_API_KEY`` environment variable; an empty string is used when
    the variable is absent (public access with reduced rate limits).
    """
    import os

    api_key = os.environ.get("PATENTSVIEW_API_KEY", "")
    log = logger.bind(user_id=user_id, art_unit=art_unit)
    log.info("examiner.art_unit.start")

    try:
        stats = await get_examiner_stats(art_unit=art_unit, api_key=api_key)
    except RuntimeError as exc:
        log.error("examiner.art_unit.error", error=str(exc))
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    log.info("examiner.art_unit.complete", count=len(stats))
    return stats


@router.get("/{examiner_id}", response_model=ExaminerStats)
async def get_examiner(
    examiner_id: str,
    user_id: str = Depends(get_user_id),
) -> ExaminerStats:
    """Return statistics for a specific examiner by their PatentsView examiner ID."""
    import os

    api_key = os.environ.get("PATENTSVIEW_API_KEY", "")
    log = logger.bind(user_id=user_id, examiner_id=examiner_id)
    log.info("examiner.lookup.start")

    try:
        stats = await lookup_examiner(examiner_id=examiner_id, api_key=api_key)
    except ValueError as exc:
        log.warning("examiner.lookup.not_found", examiner_id=examiner_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        log.error("examiner.lookup.error", error=str(exc))
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    log.info("examiner.lookup.complete", examiner_id=examiner_id)
    return stats
