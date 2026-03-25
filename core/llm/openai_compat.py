from __future__ import annotations
from openai import AsyncOpenAI
import structlog
from core.llm.base import LLMProvider, LLMResponse

logger = structlog.get_logger(__name__)


class OpenAICompatProvider(LLMProvider):
    provider_name = "openai_compat"

    def __init__(self, api_key: str = "not-needed", base_url: str = "http://localhost:11434/v1", model: str = "llama3.1", **kwargs):
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate(self, prompt: str, system: str | None = None, max_tokens: int = 4096, temperature: float = 0.0) -> LLMResponse:
        logger.info("llm.generate", provider="openai_compat", model=self.model, prompt_length=len(prompt))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            response = await self._client.chat.completions.create(model=self.model, messages=messages, max_tokens=max_tokens, temperature=temperature)
            choice = response.choices[0]
            tokens = response.usage.total_tokens if response.usage else 0
            result = LLMResponse(content=choice.message.content or "", model=response.model or self.model, tokens_used=tokens)
            logger.info("llm.generate.complete", provider="openai_compat", tokens_used=result.tokens_used)
            return result
        except Exception as e:
            logger.error("llm.generate.failed", provider="openai_compat", error=str(e))
            raise

    async def generate_with_thinking(self, prompt: str, system: str | None = None, max_tokens: int = 16000, thinking_budget: int = 10000) -> LLMResponse:
        return await self.generate(prompt, system, max_tokens, temperature=0.0)
