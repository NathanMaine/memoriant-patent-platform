"""Analyze route — POST /analyze."""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends

from api.deps import get_analyzers, get_user_id
from api.schemas.requests import AnalyzeRequest
from api.schemas.responses import AnalyzeResponse

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse, tags=["analyze"])
async def analyze(
    request: AnalyzeRequest,
    user_id: str = Depends(get_user_id),
    analyzers: dict = Depends(get_analyzers),
) -> AnalyzeResponse:
    """Run requested analysis checks against an invention description."""
    log = logger.bind(user_id=user_id, project_id=request.project_id)
    log.info("analyze.start", checks=request.checks)

    analysis_id = str(uuid.uuid4())
    checks_completed: list[str] = []
    summaries: list[str] = []

    for check in request.checks:
        module = analyzers.get(check)
        if module is None:
            log.warning("analyze.module_not_found", check=check)
            continue

        log.info("analyze.module.start", check=check)
        result = await module.analyze(
            invention_description=request.invention_description,
            search_results=[],
        )
        checks_completed.append(check)
        summaries.append(f"{check}: {result.recommendation}")
        log.info("analyze.module.complete", check=check, status=result.status)

    summary = "; ".join(summaries) if summaries else "No checks completed."
    log.info("analyze.complete", checks_completed=checks_completed)

    return AnalyzeResponse(
        project_id=request.project_id,
        analysis_id=analysis_id,
        checks_completed=checks_completed,
        summary=summary,
    )
