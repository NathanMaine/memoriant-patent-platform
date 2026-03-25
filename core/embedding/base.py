from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    provider_name: str
    dimensions: int

    @abstractmethod
    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        """Embed a list of texts.

        Args:
            texts: The texts to embed.
            input_type: Either ``"query"`` or ``"document"``.  Providers may
                use this hint to apply different prefixes or API parameters.

        Returns:
            A list of float vectors, one per input text.
        """
        ...
