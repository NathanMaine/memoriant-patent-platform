from __future__ import annotations
from core.llm.base import LLMProvider
from core.llm.claude import ClaudeProvider
from core.llm.openai_compat import OpenAICompatProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "claude": ClaudeProvider,
    "openai_compat": OpenAICompatProvider,
    "ollama": OpenAICompatProvider,
    "vllm": OpenAICompatProvider,
    "lm_studio": OpenAICompatProvider,
}

class LLMRegistry:
    @staticmethod
    def create(provider: str, **kwargs) -> LLMProvider:
        cls = _PROVIDERS.get(provider)
        if cls is None:
            raise ValueError(f"Unknown LLM provider: {provider}")
        return cls(**kwargs)

    @staticmethod
    def list_providers() -> list[str]:
        return list(_PROVIDERS.keys())
