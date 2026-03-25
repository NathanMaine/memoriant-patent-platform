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


@pytest.mark.asyncio
async def test_openai_compat_generate_with_system(ollama_provider):
    provider, mock_client = ollama_provider
    mock_choice = MagicMock()
    mock_choice.message.content = "System-guided result"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.model = "llama3.1"
    mock_response.usage.total_tokens = 120

    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    result = await provider.generate("Analyze this patent", system="You are a patent expert.")

    assert result.content == "System-guided result"
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a patent expert."
    assert messages[1]["role"] == "user"


@pytest.mark.asyncio
async def test_openai_compat_constructor_direct():
    with patch("core.llm.openai_compat.AsyncOpenAI") as mock_cls:
        mock_cls.return_value = MagicMock()
        provider = OpenAICompatProvider(
            api_key="my-key",
            base_url="http://10.0.4.93:1234/v1",
            model="qwen2.5",
        )
    assert provider.model == "qwen2.5"


@pytest.mark.asyncio
async def test_openai_compat_generate_raises_on_api_error(ollama_provider):
    provider, mock_client = ollama_provider
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Connection refused"))
    with pytest.raises(Exception, match="Connection refused"):
        await provider.generate("Analyze this patent")
