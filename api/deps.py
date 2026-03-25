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


def get_aggregator():
    """Build a default SearchAggregator with no providers (no-op in tests; override in prod)."""
    from core.search.aggregator import SearchAggregator
    return SearchAggregator(providers=[])


def get_analyzers() -> dict:
    """Return a dict mapping check name → AnalysisModule (empty by default; override in tests)."""
    return {}


def get_drafter():
    """Return a provisional drafter stub (no real LLM; override in tests/prod)."""
    from core.drafting.provisional import ProvisionalDrafter

    class _NoopLLM:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("No LLM configured — inject via dependency_overrides")

    return ProvisionalDrafter(llm_provider=_NoopLLM())  # type: ignore[arg-type]


def get_pipeline():
    """Return a PatentPipeline instance (no-op config; override in tests/prod)."""
    from core.pipeline import PatentPipeline
    from core.search.aggregator import SearchAggregator
    from core.drafting.provisional import ProvisionalDrafter

    class _NoopLLM:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("No LLM configured — inject via dependency_overrides")

    return PatentPipeline(
        llm_provider=_NoopLLM(),  # type: ignore[arg-type]
        search_aggregator=SearchAggregator(providers=[]),
        analysis_modules=[],
        drafter=ProvisionalDrafter(llm_provider=_NoopLLM()),  # type: ignore[arg-type]
    )
