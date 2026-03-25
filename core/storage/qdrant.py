from __future__ import annotations
from qdrant_client import AsyncQdrantClient, models

COLLECTION_NAME = "patent_embeddings"


class QdrantStorage:
    def __init__(self, host: str = "localhost", port: int = 6333):
        self._host = host
        self._port = port
        self._client = AsyncQdrantClient(host=host, port=port)

    async def initialize(self, dimensions: int = 1536) -> None:
        exists = await self._client.collection_exists(COLLECTION_NAME)
        if not exists:
            await self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=dimensions,
                    distance=models.Distance.COSINE,
                ),
            )

    async def upsert(self, point_id: str, vector: list[float], payload: dict) -> None:
        await self._client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(id=point_id, vector=vector, payload=payload),
            ],
        )

    async def search(
        self, query_vector: list[float], limit: int = 10, filters: dict | None = None,
    ) -> list[dict]:
        query_filter = None
        if filters:
            conditions = [
                models.FieldCondition(key=k, match=models.MatchValue(value=v))
                for k, v in filters.items()
            ]
            query_filter = models.Filter(must=conditions)

        results = await self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            query_filter=query_filter,
        )
        return [
            {"id": str(point.id), "score": point.score, **point.payload}
            for point in results.points
        ]

    async def close(self) -> None:
        await self._client.close()
