"""Pipeline route — POST /pipeline."""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends

from api.deps import get_pipeline, get_user_id
from api.schemas.requests import PipelineRequest
from api.schemas.responses import PipelineResponse

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/pipeline", response_model=PipelineResponse, tags=["pipeline"])
async def pipeline(
    request: PipelineRequest,
    user_id: str = Depends(get_user_id),
    pipeline_instance=Depends(get_pipeline),
) -> PipelineResponse:
    """Run the full patent pipeline end-to-end and return the result."""
    project_id = request.project_id or str(uuid.uuid4())
    pipeline_id = str(uuid.uuid4())

    log = logger.bind(user_id=user_id, project_id=project_id, pipeline_id=pipeline_id)
    log.info("pipeline.start")

    result = await pipeline_instance.run(
        invention_description=request.invention_description,
        filing_format=request.filing_format,
        project_id=project_id,
        resume_from=request.resume_from,
        user_override=request.user_override,
    )

    status = result.current_stage
    log.info("pipeline.complete", status=status, stages=result.stages_completed)

    return PipelineResponse(
        project_id=result.project_id,
        pipeline_id=pipeline_id,
        status=status,
        stages_completed=result.stages_completed,
    )
