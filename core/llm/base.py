from __future__ import annotations
from abc import ABC, abstractmethod
from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    model: str
    tokens_used: int
    thinking: str | None = None


class LLMProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None, max_tokens: int = 4096, temperature: float = 0.0) -> LLMResponse: ...

    @abstractmethod
    async def generate_with_thinking(self, prompt: str, system: str | None = None, max_tokens: int = 16000, thinking_budget: int = 10000) -> LLMResponse: ...
