from core.models.config import UserConfig, LLMProviderConfig, SearchProviderConfig


def test_default_config():
    cfg = UserConfig()
    assert cfg.llm.provider == "claude"
    assert cfg.llm.model == "claude-opus-4-6"
    assert cfg.llm.extended_thinking is True


def test_ollama_config():
    cfg = UserConfig(
        llm=LLMProviderConfig(
            provider="ollama",
            endpoint="http://10.0.4.93:11434",
            model="llama3.1:70b",
            extended_thinking=False,
        )
    )
    assert cfg.llm.provider == "ollama"
    assert cfg.llm.endpoint == "http://10.0.4.93:11434"


def test_search_config_defaults():
    cfg = UserConfig()
    assert cfg.search.patentsview_enabled is True
    assert cfg.search.uspto_odp_enabled is True
    assert cfg.search.serpapi_enabled is False


def test_search_config_paid_requires_key():
    cfg = UserConfig(
        search=SearchProviderConfig(serpapi_enabled=True, serpapi_key="sk-test")
    )
    assert cfg.search.serpapi_enabled is True
