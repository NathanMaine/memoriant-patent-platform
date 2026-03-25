from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.embedding.openai_embed import OpenAIEmbeddingProvider


@pytest.fixture
def openai_provider():
    with patch("core.embedding.openai_embed.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        provider._client = mock_client
        yield provider, mock_client


def _make_embed_response(vectors: list[list[float]]):
    mock_response = MagicMock()
    mock_response.data = []
    for vec in vectors:
        item = MagicMock()
        item.embedding = vec
        mock_response.data.append(item)
    return mock_response


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def test_openai_provider_name(openai_provider):
    provider, _ = openai_provider
    assert provider.provider_name == "openai"


def test_openai_provider_dimensions(openai_provider):
    provider, _ = openai_provider
    assert provider.dimensions == 1536


def test_openai_provider_default_model(openai_provider):
    provider, _ = openai_provider
    assert provider.model == "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embed_single_text_returns_correct_dimensions(openai_provider):
    provider, mock_client = openai_provider
    vector = [0.1] * 1536
    mock_client.embeddings.create = AsyncMock(return_value=_make_embed_response([vector]))

    result = await provider.embed(["Hello patent world"])

    assert len(result) == 1
    assert len(result[0]) == 1536


@pytest.mark.asyncio
async def test_embed_batch_multiple_texts(openai_provider):
    provider, mock_client = openai_provider
    vectors = [[float(i)] * 1536 for i in range(3)]
    mock_client.embeddings.create = AsyncMock(return_value=_make_embed_response(vectors))

    result = await provider.embed(["text one", "text two", "text three"])

    assert len(result) == 3
    assert result[0][0] == 0.0
    assert result[1][0] == 1.0
    assert result[2][0] == 2.0


@pytest.mark.asyncio
async def test_embed_passes_texts_to_api(openai_provider):
    provider, mock_client = openai_provider
    mock_client.embeddings.create = AsyncMock(return_value=_make_embed_response([[0.0] * 1536]))

    await provider.embed(["patent claim text"])

    call_kwargs = mock_client.embeddings.create.call_args.kwargs
    assert "patent claim text" in call_kwargs["input"]


@pytest.mark.asyncio
async def test_embed_uses_correct_model(openai_provider):
    provider, mock_client = openai_provider
    mock_client.embeddings.create = AsyncMock(return_value=_make_embed_response([[0.0] * 1536]))

    await provider.embed(["text"])

    call_kwargs = mock_client.embeddings.create.call_args.kwargs
    assert call_kwargs["model"] == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_embed_raises_on_api_error(openai_provider):
    provider, mock_client = openai_provider
    mock_client.embeddings.create = AsyncMock(side_effect=Exception("API unavailable"))

    with pytest.raises(Exception, match="API unavailable"):
        await provider.embed(["some text"])


@pytest.mark.asyncio
async def test_embed_document_input_type(openai_provider):
    provider, mock_client = openai_provider
    mock_client.embeddings.create = AsyncMock(return_value=_make_embed_response([[0.0] * 1536]))

    await provider.embed(["document text"], input_type="document")

    assert mock_client.embeddings.create.called


@pytest.mark.asyncio
async def test_embed_query_input_type(openai_provider):
    provider, mock_client = openai_provider
    mock_client.embeddings.create = AsyncMock(return_value=_make_embed_response([[0.0] * 1536]))

    await provider.embed(["query text"], input_type="query")

    assert mock_client.embeddings.create.called
