from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.embedding.ollama_embed import OllamaEmbeddingProvider


@pytest.fixture
def ollama_provider():
    with patch("core.embedding.ollama_embed.httpx.AsyncClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        provider = OllamaEmbeddingProvider()
        yield provider, mock_client


def _make_httpx_response(embeddings: list[list[float]]):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"embeddings": embeddings})
    return mock_resp


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def test_ollama_provider_name():
    provider = OllamaEmbeddingProvider()
    assert provider.provider_name == "ollama"


def test_ollama_provider_dimensions():
    provider = OllamaEmbeddingProvider()
    assert provider.dimensions == 768


def test_ollama_provider_default_model():
    provider = OllamaEmbeddingProvider()
    assert provider.model == "nomic-embed-text"


# ---------------------------------------------------------------------------
# Prefix behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embed_document_adds_search_document_prefix(ollama_provider):
    provider, mock_client = ollama_provider
    vector = [0.1] * 768
    mock_client.post = AsyncMock(return_value=_make_httpx_response([vector]))

    await provider.embed(["A patent claim"], input_type="document")

    call_kwargs = mock_client.post.call_args.kwargs
    sent_inputs = call_kwargs["json"]["input"]
    assert sent_inputs[0].startswith("search_document: ")


@pytest.mark.asyncio
async def test_embed_query_adds_search_query_prefix(ollama_provider):
    provider, mock_client = ollama_provider
    vector = [0.1] * 768
    mock_client.post = AsyncMock(return_value=_make_httpx_response([vector]))

    await provider.embed(["Find me patents about widgets"], input_type="query")

    call_kwargs = mock_client.post.call_args.kwargs
    sent_inputs = call_kwargs["json"]["input"]
    assert sent_inputs[0].startswith("search_query: ")


# ---------------------------------------------------------------------------
# Embedding output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embed_single_text_returns_correct_dimensions(ollama_provider):
    provider, mock_client = ollama_provider
    vector = [0.5] * 768
    mock_client.post = AsyncMock(return_value=_make_httpx_response([vector]))

    result = await provider.embed(["hello"])

    assert len(result) == 1
    assert len(result[0]) == 768


@pytest.mark.asyncio
async def test_embed_batch_multiple_texts(ollama_provider):
    provider, mock_client = ollama_provider
    vectors = [[float(i)] * 768 for i in range(3)]
    mock_client.post = AsyncMock(return_value=_make_httpx_response(vectors))

    result = await provider.embed(["a", "b", "c"])

    assert len(result) == 3
    assert result[0][0] == 0.0
    assert result[1][0] == 1.0
    assert result[2][0] == 2.0


@pytest.mark.asyncio
async def test_embed_posts_to_correct_endpoint(ollama_provider):
    provider, mock_client = ollama_provider
    mock_client.post = AsyncMock(return_value=_make_httpx_response([[0.0] * 768]))

    await provider.embed(["text"])

    call_args = mock_client.post.call_args
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
    assert "/api/embed" in url


@pytest.mark.asyncio
async def test_embed_raises_on_http_error(ollama_provider):
    provider, mock_client = ollama_provider
    mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

    with pytest.raises(Exception, match="Connection refused"):
        await provider.embed(["some text"])


@pytest.mark.asyncio
async def test_embed_raises_for_status_on_bad_response(ollama_provider):
    provider, mock_client = ollama_provider
    bad_response = MagicMock()
    bad_response.raise_for_status = MagicMock(side_effect=Exception("404 Not Found"))
    bad_response.json = MagicMock(return_value={})
    mock_client.post = AsyncMock(return_value=bad_response)

    with pytest.raises(Exception, match="404 Not Found"):
        await provider.embed(["text"])
