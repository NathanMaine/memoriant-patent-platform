"""Search route — POST /search."""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends

from api.deps import get_aggregator, get_user_id
from api.schemas.requests import SearchRequest
from api.schemas.responses import SearchResponse
from core.search.base import SearchQuery

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/search", response_model=SearchResponse, tags=["search"])
async def search(
    request: SearchRequest,
    user_id: str = Depends(get_user_id),
    aggregator=Depends(get_aggregator),
) -> SearchResponse:
    """Run a patent search across configured providers."""
    project_id = request.project_id or str(uuid.uuid4())
    log = logger.bind(user_id=user_id, project_id=project_id, query=request.query)
    log.info("search.start")

    query = SearchQuery(
        query=request.query,
        strategies=request.strategies,
        date_range=request.date_range,
        cpc_codes=request.cpc_codes,
        max_results=request.max_results,
    )

    agg_response = await aggregator.search(query)

    results = [r.model_dump(mode="json") for r in agg_response.results]
    log.info("search.complete", total=len(results))

    return SearchResponse(
        project_id=project_id,
        query=request.query,
        results=results,
        total=len(results),
        strategies_used=request.strategies,
    )
