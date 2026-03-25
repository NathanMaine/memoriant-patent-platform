from __future__ import annotations

import structlog
from openai import AsyncOpenAI

from core.embedding.base import EmbeddingProvider

logger = structlog.get_logger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by the OpenAI Embeddings API.

    Default model: ``text-embedding-3-small`` (1536 dimensions).
    """

    provider_name = "openai"
    dimensions = 1536

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
    ) -> None:
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key) if api_key else AsyncOpenAI()

    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        """Embed *texts* using the OpenAI embeddings API.

        Args:
            texts: Texts to embed.
            input_type: ``"query"`` or ``"document"`` (informational; the
                OpenAI API does not have a separate parameter for this).

        Returns:
            A list of float vectors with :attr:`dimensions` elements each.
        """
        logger.info(
            "embedding.openai.embed",
            model=self.model,
            num_texts=len(texts),
            input_type=input_type,
        )
        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=texts,
            )
            result = [item.embedding for item in response.data]
            logger.info(
                "embedding.openai.embed.complete",
                model=self.model,
                num_embeddings=len(result),
            )
            return result
        except Exception as exc:
            logger.error("embedding.openai.embed.failed", model=self.model, error=str(exc))
            raise
