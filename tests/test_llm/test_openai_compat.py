import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.llm.openai_compat import OpenAICompatProvider
from core.llm.base import LLMResponse


@pytest.fixture
def ollama_provider():
    with patch("core.llm.openai_compat.AsyncOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        provider = OpenAICompatProvider(
            base_url="http://10.0.4.93:11434/v1",
            model="llama3.1",
        )
        provider._client = mock_client
        yield provider, mock_client


@pytest.mark.asyncio
async def test_openai_compat_init(ollama_provider):
    provider, _ = ollama_provider
    assert provider.model == "llama3.1"
    assert provider.provider_name == "openai_compat"


@pytest.mark.asyncio
async def test_openai_compat_generate(ollama_provider):
    provider, mock_client = ollama_provider
    mock_choice = MagicMock()
    mock_choice.message.content = "Analysis result"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.model = "llama3.1"
    mock_response.usage.total_tokens = 150

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    result = await provider.generate("Analyze this patent")

    assert isinstance(result, LLMResponse)
    assert result.content == "Analysis result"
    assert result.tokens_used == 150


@pytest.mark.asyncio
async def test_generate_with_thinking_falls_back(ollama_provider):
    provider, mock_client = ollama_provider
    mock_choice = MagicMock()
    mock_choice.message.content = "Fallback result"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.model = "llama3.1"
    mock_response.usage.total_tokens = 100

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    result = await provider.generate_with_thinking("Analyze this")

    assert result.content == "Fallback result"
    assert result.thinking is None
