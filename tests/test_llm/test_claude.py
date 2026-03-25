import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.llm.claude import ClaudeProvider
from core.llm.base import LLMResponse


@pytest.fixture
def claude_provider():
    return ClaudeProvider(api_key="test-key", model="claude-opus-4-6")


def test_claude_provider_init(claude_provider):
    assert claude_provider.model == "claude-opus-4-6"
    assert claude_provider.provider_name == "claude"


@pytest.mark.asyncio
async def test_claude_generate(claude_provider):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Patent analysis result")]
    mock_response.model = "claude-opus-4-6"
    mock_response.usage.input_tokens = 50
    mock_response.usage.output_tokens = 100

    with patch.object(claude_provider._client, "messages", create=True) as mock_messages:
        mock_messages.create = AsyncMock(return_value=mock_response)
        result = await claude_provider.generate("Analyze this patent claim")

    assert isinstance(result, LLMResponse)
    assert result.content == "Patent analysis result"


@pytest.mark.asyncio
async def test_claude_generate_with_system(claude_provider):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Result with system prompt")]
    mock_response.model = "claude-opus-4-6"
    mock_response.usage.input_tokens = 60
    mock_response.usage.output_tokens = 110

    with patch.object(claude_provider._client, "messages", create=True) as mock_messages:
        mock_messages.create = AsyncMock(return_value=mock_response)
        result = await claude_provider.generate(
            "Analyze this patent claim", system="You are a patent expert."
        )

    assert result.content == "Result with system prompt"
    call_kwargs = mock_messages.create.call_args.kwargs
    assert call_kwargs["system"] == "You are a patent expert."


@pytest.mark.asyncio
async def test_claude_generate_with_thinking(claude_provider):
    thinking_block = MagicMock()
    thinking_block.type = "thinking"
    thinking_block.thinking = "Let me reason through the claims carefully..."

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Based on my analysis, the claims are novel."

    mock_response = MagicMock()
    mock_response.content = [thinking_block, text_block]
    mock_response.model = "claude-opus-4-6"
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 200

    with patch.object(claude_provider._client, "messages", create=True) as mock_messages:
        mock_messages.create = AsyncMock(return_value=mock_response)
        result = await claude_provider.generate_with_thinking(
            "Analyze this patent claim", system="You are a patent expert."
        )

    assert isinstance(result, LLMResponse)
    assert result.content == "Based on my analysis, the claims are novel."
    assert result.thinking == "Let me reason through the claims carefully..."
    assert result.tokens_used == 300


@pytest.mark.asyncio
async def test_claude_generate_raises_on_api_error(claude_provider):
    with patch.object(claude_provider._client, "messages", create=True) as mock_messages:
        mock_messages.create = AsyncMock(side_effect=Exception("API error"))
        with pytest.raises(Exception, match="API error"):
            await claude_provider.generate("Analyze this patent claim")


@pytest.mark.asyncio
async def test_claude_generate_with_thinking_raises_on_api_error(claude_provider):
    with patch.object(claude_provider._client, "messages", create=True) as mock_messages:
        mock_messages.create = AsyncMock(side_effect=Exception("Thinking API error"))
        with pytest.raises(Exception, match="Thinking API error"):
            await claude_provider.generate_with_thinking("Analyze this patent claim")
