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
