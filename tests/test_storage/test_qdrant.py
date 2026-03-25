import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.storage.qdrant import QdrantStorage


@pytest.fixture
def qdrant_storage():
    with patch("core.storage.qdrant.AsyncQdrantClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        storage = QdrantStorage(host="localhost", port=6333)
        storage._client = mock_client
        yield storage, mock_client


@pytest.mark.asyncio
async def test_initialize_creates_collection(qdrant_storage):
    storage, mock_client = qdrant_storage
    mock_client.collection_exists = AsyncMock(return_value=False)
    mock_client.create_collection = AsyncMock()
    await storage.initialize(dimensions=1536)
    mock_client.create_collection.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_embedding(qdrant_storage):
    storage, mock_client = qdrant_storage
    mock_client.upsert = AsyncMock()
    await storage.upsert(
        point_id="test-id",
        vector=[0.1] * 1536,
        payload={"patent_id": "US11234567", "chunk_type": "abstract", "text": "A system..."},
    )
    mock_client.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_search_returns_results(qdrant_storage):
    storage, mock_client = qdrant_storage
    mock_point = MagicMock()
    mock_point.id = "test-id"
    mock_point.score = 0.95
    mock_point.payload = {"patent_id": "US11234567", "text": "A system..."}
    mock_client.query_points = AsyncMock(return_value=MagicMock(points=[mock_point]))

    results = await storage.search(query_vector=[0.1] * 1536, limit=5)
    assert len(results) == 1
    assert results[0]["patent_id"] == "US11234567"
    assert results[0]["score"] == 0.95


@pytest.mark.asyncio
async def test_search_with_filters(qdrant_storage):
    storage, mock_client = qdrant_storage
    mock_point = MagicMock()
    mock_point.id = "filtered-id"
    mock_point.score = 0.88
    mock_point.payload = {"patent_id": "US99887766", "chunk_type": "abstract"}
    mock_client.query_points = AsyncMock(return_value=MagicMock(points=[mock_point]))

    results = await storage.search(
        query_vector=[0.2] * 1536, limit=3, filters={"chunk_type": "abstract"}
    )
    assert len(results) == 1
    assert results[0]["patent_id"] == "US99887766"
    call_kwargs = mock_client.query_points.call_args.kwargs
    assert call_kwargs["query_filter"] is not None


@pytest.mark.asyncio
async def test_close(qdrant_storage):
    storage, mock_client = qdrant_storage
    mock_client.close = AsyncMock()
    await storage.close()
    mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_skips_creation_when_collection_exists(qdrant_storage):
    storage, mock_client = qdrant_storage
    mock_client.collection_exists = AsyncMock(return_value=True)
    mock_client.create_collection = AsyncMock()
    await storage.initialize(dimensions=1536)
    mock_client.create_collection.assert_not_called()
