import pytest
from core.llm.base import LLMProvider, LLMResponse


def test_llm_response_model():
    resp = LLMResponse(content="Hello", model="claude-opus-4-6", tokens_used=100)
    assert resp.content == "Hello"
    assert resp.tokens_used == 100


def test_llm_provider_is_abstract():
    with pytest.raises(TypeError):
        LLMProvider()
