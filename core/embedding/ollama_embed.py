from __future__ import annotations

import httpx
import structlog

from core.embedding.base import EmbeddingProvider

logger = structlog.get_logger(__name__)

_PREFIX_MAP = {
    "query": "search_query: ",
    "document": "search_document: ",
}


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by a local Ollama ``/api/embed`` endpoint.

    Default model: ``nomic-embed-text`` (768 dimensions).

    Per spec Appendix B, texts are prefixed with ``"search_query: "`` or
    ``"search_document: "`` depending on *input_type* to guide the model.
    """

    provider_name = "ollama"
    dimensions = 768

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        """Embed *texts* via the Ollama ``/api/embed`` endpoint.

        Args:
            texts: Texts to embed.
            input_type: ``"query"`` or ``"document"``.  Controls which Nomic
                prefix is prepended to each text.

        Returns:
            A list of float vectors with :attr:`dimensions` elements each.
        """
        prefix = _PREFIX_MAP.get(input_type, _PREFIX_MAP["document"])
        prefixed = [prefix + t for t in texts]

        logger.info(
            "embedding.ollama.embed",
            model=self.model,
            num_texts=len(texts),
            input_type=input_type,
            prefix=prefix,
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url=f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": prefixed},
                )
                response.raise_for_status()
                data = response.json()

            result: list[list[float]] = data["embeddings"]
            logger.info(
                "embedding.ollama.embed.complete",
                model=self.model,
                num_embeddings=len(result),
            )
            return result
        except Exception as exc:
            logger.error("embedding.ollama.embed.failed", model=self.model, error=str(exc))
            raise
