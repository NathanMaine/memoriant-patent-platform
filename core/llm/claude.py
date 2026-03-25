from __future__ import annotations
import anthropic
import structlog
from core.llm.base import LLMProvider, LLMResponse

logger = structlog.get_logger(__name__)


class ClaudeProvider(LLMProvider):
    provider_name = "claude"

    def __init__(self, api_key: str, model: str = "claude-opus-4-6"):
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(self, prompt: str, system: str | None = None, max_tokens: int = 4096, temperature: float = 0.0) -> LLMResponse:
        logger.info("llm.generate", provider="claude", model=self.model, prompt_length=len(prompt))
        kwargs = {"model": self.model, "max_tokens": max_tokens, "temperature": temperature, "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        try:
            response = await self._client.messages.create(**kwargs)
            result = LLMResponse(content=response.content[0].text, model=response.model, tokens_used=response.usage.input_tokens + response.usage.output_tokens)
            logger.info("llm.generate.complete", provider="claude", tokens_used=result.tokens_used)
            return result
        except Exception as e:
            logger.error("llm.generate.failed", provider="claude", error=str(e))
            raise

    async def generate_with_thinking(self, prompt: str, system: str | None = None, max_tokens: int = 16000, thinking_budget: int = 10000) -> LLMResponse:
        logger.info("llm.generate", provider="claude", model=self.model, prompt_length=len(prompt))
        kwargs = {"model": self.model, "max_tokens": max_tokens, "temperature": 1.0, "thinking": {"type": "enabled", "budget_tokens": thinking_budget}, "messages": [{"role": "user", "content": prompt}]}
        if system:
            kwargs["system"] = system
        try:
            response = await self._client.messages.create(**kwargs)
            thinking_text = None
            content_text = ""
            for block in response.content:
                if block.type == "thinking":
                    thinking_text = block.thinking
                elif block.type == "text":
                    content_text = block.text
            result = LLMResponse(content=content_text, model=response.model, tokens_used=response.usage.input_tokens + response.usage.output_tokens, thinking=thinking_text)
            logger.info("llm.generate.complete", provider="claude", tokens_used=result.tokens_used)
            return result
        except Exception as e:
            logger.error("llm.generate.failed", provider="claude", error=str(e))
            raise
