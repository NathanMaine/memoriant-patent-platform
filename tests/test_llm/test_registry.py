import pytest
from core.llm.registry import LLMRegistry
from core.llm.claude import ClaudeProvider


def test_registry_create_claude():
    provider = LLMRegistry.create("claude", api_key="test-key")
    assert isinstance(provider, ClaudeProvider)


def test_registry_unknown_provider():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        LLMRegistry.create("unknown_provider")


def test_registry_list_providers():
    providers = LLMRegistry.list_providers()
    assert "claude" in providers
    assert "openai_compat" in providers
