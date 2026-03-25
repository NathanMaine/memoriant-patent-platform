"""Config routes — GET /config and PUT /config."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends

from api.deps import get_config, get_user_id
from api.schemas.requests import ConfigUpdateRequest
from api.schemas.responses import ConfigUpdateResponse
from core.models.config import UserConfig

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/config", response_model=UserConfig, tags=["config"])
async def get_user_config(
    user_id: str = Depends(get_user_id),
    config: UserConfig = Depends(get_config),
) -> UserConfig:
    """Return the current user configuration."""
    logger.info("config.get", user_id=user_id)
    return config


@router.put("/config", response_model=ConfigUpdateResponse, tags=["config"])
async def update_config(
    update: ConfigUpdateRequest,
    user_id: str = Depends(get_user_id),
    config: UserConfig = Depends(get_config),
) -> ConfigUpdateResponse:
    """Apply a partial config update and return the list of updated fields."""
    log = logger.bind(user_id=user_id)
    log.info("config.update.start")

    updated_fields: list[str] = []

    if update.llm_provider is not None:
        config.llm.provider = update.llm_provider
        updated_fields.append("llm_provider")

    if update.llm_model is not None:
        config.llm.model = update.llm_model
        updated_fields.append("llm_model")

    if update.llm_endpoint is not None:
        config.llm.endpoint = update.llm_endpoint
        updated_fields.append("llm_endpoint")

    if update.patentsview_api_key is not None:
        config.search.patentsview_api_key = update.patentsview_api_key
        updated_fields.append("patentsview_api_key")

    if update.serpapi_key is not None:
        config.search.serpapi_key = update.serpapi_key
        updated_fields.append("serpapi_key")

    log.info("config.update.complete", updated_fields=updated_fields)
    return ConfigUpdateResponse(
        updated_fields=updated_fields,
        message=f"Updated {len(updated_fields)} field(s).",
    )
