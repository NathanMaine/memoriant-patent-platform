"""Health check route."""
from __future__ import annotations

import structlog
from fastapi import APIRouter

from api.schemas.responses import HealthResponse

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Return API health status, version, and service info."""
    logger.debug("api.health_check")
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        services={"api": "running"},
    )
