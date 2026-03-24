from __future__ import annotations
import anthropic
from core.llm.base import LLMProvider, LLMResponse


class ClaudeProvider(LLMProvider):
    provider_name = "claude"

    def __init__(self, api_key: str, model: str = "claude-opus-4-6"):
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(self, prompt: str, system: str | None = None, max_tokens: int = 4096, temperature: float = 0.0) -> LLMResponse:
        kwargs = {"model": self.model, "max_tokens": max_tokens, "temperature": temperature, "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        response = await self._client.messages.create(**kwargs)
        return LLMResponse(content=response.content[0].text, model=response.model, tokens_used=response.usage.input_tokens + response.usage.output_tokens)

    async def generate_with_thinking(self, prompt: str, system: str | None = None, max_tokens: int = 16000, thinking_budget: int = 10000) -> LLMResponse:
        kwargs = {"model": self.model, "max_tokens": max_tokens, "temperature": 1.0, "thinking": {"type": "enabled", "budget_tokens": thinking_budget}, "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        response = await self._client.messages.create(**kwargs)
        thinking_text = None
        content_text = ""
        for block in response.content:
            if block.type == "thinking":
                thinking_text = block.thinking
            elif block.type == "text":
                content_text = block.text
        return LLMResponse(content=content_text, model=response.model, tokens_used=response.usage.input_tokens + response.usage.output_tokens, thinking=thinking_text)
