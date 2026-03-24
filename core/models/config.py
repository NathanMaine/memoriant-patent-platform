from __future__ import annotations

from pydantic import BaseModel


class LLMProviderConfig(BaseModel):
    provider: str = "claude"
    endpoint: str | None = None
    model: str = "claude-opus-4-6"
    extended_thinking: bool = True
    max_tokens: int = 128000
    api_key: str | None = None


class SearchProviderConfig(BaseModel):
    patentsview_enabled: bool = True
    patentsview_api_key: str | None = None
    uspto_odp_enabled: bool = True
    serpapi_enabled: bool = False
    serpapi_key: str | None = None


class EmbeddingConfig(BaseModel):
    provider: str = "openai"
    model: str = "text-embedding-3-small"
    dimensions: int = 1536


class StorageConfig(BaseModel):
    backend: str = "supabase"
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    sqlite_path: str = "~/.memoriant-patent/data.db"


class UserConfig(BaseModel):
    llm: LLMProviderConfig = LLMProviderConfig()
    search: SearchProviderConfig = SearchProviderConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    storage: StorageConfig = StorageConfig()
