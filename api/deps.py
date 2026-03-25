"""FastAPI dependency injection functions."""
from __future__ import annotations

import os

import structlog
from fastapi import Request

from core.models.config import (
    EmbeddingConfig,
    LLMProviderConfig,
    SearchProviderConfig,
    StorageConfig,
    UserConfig,
)

logger = structlog.get_logger(__name__)


def get_user_id(request: Request) -> str:
    """Extract authenticated user_id from request state (set by AuthMiddleware)."""
    return request.state.user_id


def get_config() -> UserConfig:
    """Build a UserConfig from environment variables."""
    llm = LLMProviderConfig(
        provider=os.environ.get("LLM_PROVIDER", "claude"),
        model=os.environ.get("LLM_MODEL", "claude-opus-4-6"),
        endpoint=os.environ.get("LLM_ENDPOINT"),
        api_key=os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"),
    )
    search = SearchProviderConfig(
        patentsview_api_key=os.environ.get("PATENTSVIEW_API_KEY"),
        serpapi_key=os.environ.get("SERPAPI_KEY"),
    )
    embedding = EmbeddingConfig(
        provider=os.environ.get("EMBEDDING_PROVIDER", "openai"),
        model=os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small"),
    )
    storage = StorageConfig(
        supabase_url=os.environ.get("SUPABASE_URL"),
        supabase_anon_key=os.environ.get("SUPABASE_ANON_KEY"),
        supabase_service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
    )
    config = UserConfig(llm=llm, search=search, embedding=embedding, storage=storage)
    logger.debug("deps.config_loaded", provider=llm.provider, model=llm.model)
    return config
