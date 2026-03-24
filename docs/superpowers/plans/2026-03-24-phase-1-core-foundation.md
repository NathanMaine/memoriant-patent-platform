# Phase 1: Core Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational layer — project scaffolding, domain models, LLM abstraction, storage abstraction, Docker infrastructure, and database schema — so all subsequent phases have a solid base to build on.

**Architecture:** Modular core library (`memoriant-patent-core`) with clean architecture layers. Inner layer: Pydantic domain models. Middle layer: abstract interfaces for LLM and storage. Outer layer: concrete provider implementations (Claude SDK, OpenAI-compat, Supabase Postgres, Qdrant, SQLite). Docker Compose orchestrates Supabase self-hosted + Qdrant + FastAPI stub.

**Tech Stack:** Python 3.11+, Pydantic v2, anthropic SDK, openai SDK, qdrant-client, asyncpg, aiosqlite, cryptography (Fernet/AES), FastAPI, Docker Compose, PostgreSQL 15 + pgvector, Qdrant, pytest + pytest-asyncio

---

## File Structure

```
memoriant-patent-platform/
├── core/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── patent.py              # Patent, Claim, SearchResult, Citation, Inventor, Assignee
│   │   ├── application.py         # DraftApplication, FilingFormat, Embodiment, ReviewNote
│   │   └── config.py              # UserConfig, LLMProviderConfig, SearchProviderConfig
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract LLMProvider interface
│   │   ├── claude.py              # Anthropic SDK provider
│   │   ├── openai_compat.py       # OpenAI-compatible provider (Ollama/vLLM/LM Studio)
│   │   └── registry.py            # Provider registration + factory
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract StorageProvider interface
│   │   ├── supabase_pg.py         # Postgres via Supabase
│   │   ├── qdrant.py              # Qdrant vector store
│   │   ├── sqlite.py              # SQLite local fallback
│   │   └── registry.py            # Storage provider factory
│   └── secrets/
│       ├── __init__.py
│       ├── base.py                # Abstract SecretsProvider interface
│       └── encrypted.py           # AES-256-GCM implementation
├── api/
│   ├── __init__.py
│   └── main.py                    # FastAPI stub (health endpoint only for Phase 1)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Shared fixtures
│   ├── test_models/
│   │   ├── __init__.py
│   │   ├── test_patent.py
│   │   ├── test_application.py
│   │   └── test_config.py
│   ├── test_llm/
│   │   ├── __init__.py
│   │   ├── test_base.py
│   │   ├── test_claude.py
│   │   ├── test_openai_compat.py
│   │   └── test_registry.py
│   ├── test_storage/
│   │   ├── __init__.py
│   │   ├── test_sqlite.py
│   │   ├── test_supabase_pg.py
│   │   └── test_qdrant.py
│   ├── test_secrets/
│   │   ├── __init__.py
│   │   └── test_encrypted.py
│   └── test_api/
│       ├── __init__.py
│       └── test_health.py
├── db/
│   └── init.sql                   # Full schema + RLS + indexes
├── docker-compose.yml
├── Dockerfile                     # For patent-api service
├── .env.example
├── pyproject.toml
├── .gitignore
└── LICENSE
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `core/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "memoriant-patent-core"
version = "0.1.0"
description = "Full-pipeline patent platform: idea to filing-ready draft"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
authors = [{name = "Nathan Maine"}]
dependencies = [
    "pydantic>=2.0",
    "anthropic>=0.40.0",
    "openai>=1.0",
    "httpx>=0.27",
    "qdrant-client>=1.9",
    "asyncpg>=0.29",
    "aiosqlite>=0.20",
    "cryptography>=43.0",
    "structlog>=24.0",
]

[project.optional-dependencies]
api = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "ruff>=0.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100
```

- [ ] **Step 2: Create .gitignore**

```
__pycache__/
*.pyc
.venv/
.env
*.egg-info/
dist/
build/
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
node_modules/
```

- [ ] **Step 3: Create .env.example**

```bash
# === Required ===
POSTGRES_PASSWORD=changeme
JWT_SECRET=changeme
ENCRYPTION_MASTER_KEY=  # 64-char hex string, generated on first setup

# === LLM Provider (Claude is default) ===
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-opus-4-6
CLAUDE_EXTENDED_THINKING=true
CLAUDE_MAX_TOKENS=128000

# === Alternative LLM Providers (optional) ===
# OLLAMA_BASE_URL=http://10.0.4.93:11434
# VLLM_BASE_URL=http://10.0.4.93:8000
# LM_STUDIO_BASE_URL=http://10.0.4.93:1234

# === Search Providers — Free (default on) ===
PATENTSVIEW_API_KEY=

# === Search Providers — Paid (opt-in) ===
# SERPAPI_KEY=

# === Embedding ===
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# === Secrets Backend ===
SECRETS_BACKEND=postgres

# === Qdrant ===
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# === Supabase ===
SUPABASE_URL=http://localhost:8000
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

- [ ] **Step 4: Create empty __init__.py files**

```bash
mkdir -p core/models core/llm core/storage core/secrets api tests/test_models tests/test_llm tests/test_storage tests/test_secrets tests/test_api db
touch core/__init__.py core/models/__init__.py core/llm/__init__.py core/storage/__init__.py core/secrets/__init__.py api/__init__.py tests/__init__.py tests/test_models/__init__.py tests/test_llm/__init__.py tests/test_storage/__init__.py tests/test_secrets/__init__.py tests/test_api/__init__.py
```

- [ ] **Step 5: Install dev dependencies and verify**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,api]"
pytest --co  # Should collect 0 tests, no errors
```

Expected: Clean install, `pytest --co` exits 0.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with pyproject.toml and directory structure"
```

---

### Task 2: Domain Models — Patent & Search

**Files:**
- Create: `core/models/patent.py`
- Test: `tests/test_models/test_patent.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_models/test_patent.py
import pytest
from datetime import date
from core.models.patent import (
    Inventor, Assignee, Citation, Claim, SearchResult, Patent,
    SearchStrategy, PatentType,
)


def test_inventor_creation():
    inv = Inventor(first="John", last="Smith")
    assert inv.first == "John"
    assert inv.last == "Smith"
    assert inv.full_name == "John Smith"


def test_assignee_creation():
    a = Assignee(organization="Google LLC")
    assert a.organization == "Google LLC"
    a2 = Assignee(first="Jane", last="Doe")
    assert a2.organization is None


def test_claim_independent():
    c = Claim(number=1, type="independent", text="A system comprising...")
    assert c.number == 1
    assert c.depends_on is None


def test_claim_dependent():
    c = Claim(number=2, type="dependent", depends_on=1, text="The system of claim 1, wherein...")
    assert c.depends_on == 1


def test_claim_dependent_requires_depends_on():
    with pytest.raises(ValueError):
        Claim(number=2, type="dependent", text="Missing depends_on")


def test_search_result_creation():
    sr = SearchResult(
        patent_id="US11234567",
        title="WIRELESS POWER SYSTEM",
        provider="patentsview",
        strategy=SearchStrategy.KEYWORD,
    )
    assert sr.patent_id == "US11234567"
    assert sr.relevance_score is None


def test_search_result_with_full_data():
    sr = SearchResult(
        patent_id="US11234567",
        title="WIRELESS POWER SYSTEM",
        abstract="A system for wirelessly...",
        patent_date=date(2023, 5, 15),
        inventors=[Inventor(first="John", last="Smith")],
        assignees=[Assignee(organization="MedTech Inc")],
        cpc_codes=["A61N1/372"],
        relevance_score=0.85,
        relevance_notes="Strong overlap in power transfer method",
        provider="patentsview",
        strategy=SearchStrategy.KEYWORD,
    )
    assert sr.inventors[0].full_name == "John Smith"
    assert sr.relevance_score == 0.85
    assert len(sr.cpc_codes) == 1


def test_patent_type_enum():
    assert PatentType.UTILITY == "utility"
    assert PatentType.DESIGN == "design"


def test_search_strategy_enum():
    assert SearchStrategy.KEYWORD == "keyword"
    assert SearchStrategy.CLASSIFICATION == "classification"
    assert SearchStrategy.CITATION == "citation"
    assert SearchStrategy.ASSIGNEE == "assignee"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models/test_patent.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'core.models.patent'`

- [ ] **Step 3: Write the implementation**

```python
# core/models/patent.py
from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class PatentType(StrEnum):
    UTILITY = "utility"
    DESIGN = "design"
    PLANT = "plant"
    REISSUE = "reissue"


class SearchStrategy(StrEnum):
    KEYWORD = "keyword"
    CLASSIFICATION = "classification"
    CITATION = "citation"
    ASSIGNEE = "assignee"
    INVENTOR = "inventor"
    DATE_RANGE = "date_range"
    BOOLEAN = "boolean"


class Inventor(BaseModel):
    first: str
    last: str
    city: str | None = None
    state: str | None = None
    country: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}"


class Assignee(BaseModel):
    organization: str | None = None
    first: str | None = None
    last: str | None = None


class Citation(BaseModel):
    patent_id: str
    direction: str = "backward"  # "backward" (this patent cites) or "forward" (cited by)


class Claim(BaseModel):
    number: int
    type: str  # "independent" or "dependent"
    text: str
    depends_on: int | None = None

    @model_validator(mode="after")
    def validate_dependent_claim(self):
        if self.type == "dependent" and self.depends_on is None:
            raise ValueError("Dependent claims must specify depends_on")
        return self


class SearchResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    patent_id: str
    title: str
    abstract: str | None = None
    patent_date: date | None = None
    patent_type: PatentType | None = None
    inventors: list[Inventor] = Field(default_factory=list)
    assignees: list[Assignee] = Field(default_factory=list)
    cpc_codes: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    relevance_score: float | None = None
    relevance_notes: str | None = None
    provider: str
    strategy: SearchStrategy


class Patent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    patent_id: str
    title: str
    abstract: str | None = None
    patent_date: date | None = None
    patent_type: PatentType = PatentType.UTILITY
    inventors: list[Inventor] = Field(default_factory=list)
    assignees: list[Assignee] = Field(default_factory=list)
    cpc_codes: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    num_claims: int | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models/test_patent.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/models/patent.py tests/test_models/test_patent.py
git commit -m "feat: domain models for Patent, Claim, SearchResult, Inventor, Assignee"
```

---

### Task 3: Domain Models — Application & Config

**Files:**
- Create: `core/models/application.py`
- Create: `core/models/config.py`
- Test: `tests/test_models/test_application.py`
- Test: `tests/test_models/test_config.py`

- [ ] **Step 1: Write the failing tests for application models**

```python
# tests/test_models/test_application.py
import pytest
from core.models.application import (
    DraftApplication, FilingFormat, Embodiment, ReviewNote,
    ReviewType, ReviewSeverity, Specification,
)
from core.models.patent import Claim


def test_filing_format_enum():
    assert FilingFormat.PROVISIONAL == "provisional"
    assert FilingFormat.NONPROVISIONAL == "nonprovisional"
    assert FilingFormat.PCT == "pct"


def test_embodiment():
    e = Embodiment(title="Cloud-based implementation", description="In this embodiment...")
    assert e.title == "Cloud-based implementation"


def test_specification():
    spec = Specification(
        background="The field of...",
        summary="The present invention...",
        detailed_description="Referring to FIG. 1...",
        embodiments=[Embodiment(title="First", description="...")],
    )
    assert len(spec.embodiments) == 1


def test_review_note():
    note = ReviewNote(
        type=ReviewType.NOVELTY_102,
        finding="Claim 1 anticipated by US11234567",
        severity=ReviewSeverity.HIGH,
        suggestion="Narrow claim to focus on adaptive frequency hopping",
    )
    assert note.severity == "high"


def test_draft_application_abstract_length():
    """Abstract must be 150 words or fewer."""
    short_abstract = "A system for wireless power transfer."
    app = DraftApplication(
        title="TEST",
        filing_format=FilingFormat.PROVISIONAL,
        abstract=short_abstract,
        specification=Specification(
            background="", summary="", detailed_description="", embodiments=[]
        ),
        claims=[Claim(number=1, type="independent", text="A system...")],
    )
    assert app.abstract == short_abstract


def test_draft_application_abstract_too_long():
    long_abstract = " ".join(["word"] * 200)
    with pytest.raises(ValueError, match="150 words"):
        DraftApplication(
            title="TEST",
            filing_format=FilingFormat.PROVISIONAL,
            abstract=long_abstract,
            specification=Specification(
                background="", summary="", detailed_description="", embodiments=[]
            ),
            claims=[Claim(number=1, type="independent", text="A system...")],
        )
```

- [ ] **Step 2: Write the failing tests for config models**

```python
# tests/test_models/test_config.py
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_models/ -v
```

Expected: New tests FAIL, previous patent tests still PASS.

- [ ] **Step 4: Write application.py implementation**

```python
# core/models/application.py
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from core.models.patent import Claim


class FilingFormat(StrEnum):
    PROVISIONAL = "provisional"
    NONPROVISIONAL = "nonprovisional"
    PCT = "pct"


class ReviewType(StrEnum):
    ELIGIBILITY_101 = "101"
    NOVELTY_102 = "102"
    OBVIOUSNESS_103 = "103"
    WRITTEN_DESCRIPTION_112A = "112a"
    INDEFINITENESS_112B = "112b"
    FORMALITIES = "formalities"


class ReviewSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Embodiment(BaseModel):
    title: str
    description: str


class Specification(BaseModel):
    background: str
    summary: str
    detailed_description: str
    embodiments: list[Embodiment] = Field(default_factory=list)


class ReviewNote(BaseModel):
    type: ReviewType
    finding: str
    severity: ReviewSeverity
    suggestion: str


class DraftApplication(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    version: int = 1
    filing_format: FilingFormat
    title: str
    abstract: str | None = None
    specification: Specification
    claims: list[Claim] = Field(default_factory=list)
    drawings_description: str | None = None
    ads_data: dict | None = None
    review_notes: list[ReviewNote] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("abstract")
    @classmethod
    def validate_abstract_length(cls, v: str | None) -> str | None:
        if v is not None and len(v.split()) > 150:
            raise ValueError("Abstract must be 150 words or fewer per USPTO rules")
        return v
```

- [ ] **Step 5: Write config.py implementation**

```python
# core/models/config.py
from __future__ import annotations

from pydantic import BaseModel


class LLMProviderConfig(BaseModel):
    provider: str = "claude"
    endpoint: str | None = None
    model: str = "claude-opus-4-6"
    extended_thinking: bool = True
    max_tokens: int = 128000
    api_key: str | None = None  # Resolved at runtime from secrets


class SearchProviderConfig(BaseModel):
    patentsview_enabled: bool = True
    patentsview_api_key: str | None = None
    uspto_odp_enabled: bool = True
    serpapi_enabled: bool = False
    serpapi_key: str | None = None


class EmbeddingConfig(BaseModel):
    provider: str = "openai"
    model: str = "text-embedding-3-small"
    dimensions: int = 1536


class StorageConfig(BaseModel):
    backend: str = "supabase"  # supabase, sqlite
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    sqlite_path: str = "~/.memoriant-patent/data.db"


class UserConfig(BaseModel):
    llm: LLMProviderConfig = LLMProviderConfig()
    search: SearchProviderConfig = SearchProviderConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    storage: StorageConfig = StorageConfig()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_models/ -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add core/models/ tests/test_models/
git commit -m "feat: application and config domain models with validation"
```

---

### Task 4: LLM Provider — Base Interface & Claude

**Files:**
- Create: `core/llm/base.py`
- Create: `core/llm/claude.py`
- Create: `core/llm/registry.py`
- Test: `tests/test_llm/test_base.py`
- Test: `tests/test_llm/test_claude.py`
- Test: `tests/test_llm/test_registry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_llm/test_base.py
import pytest
from core.llm.base import LLMProvider, LLMResponse


def test_llm_response_model():
    resp = LLMResponse(content="Hello", model="claude-opus-4-6", tokens_used=100)
    assert resp.content == "Hello"
    assert resp.tokens_used == 100


def test_llm_provider_is_abstract():
    with pytest.raises(TypeError):
        LLMProvider()
```

```python
# tests/test_llm/test_claude.py
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
```

```python
# tests/test_llm/test_registry.py
from core.llm.registry import LLMRegistry
from core.llm.claude import ClaudeProvider


def test_registry_create_claude():
    provider = LLMRegistry.create("claude", api_key="test-key")
    assert isinstance(provider, ClaudeProvider)


def test_registry_unknown_provider():
    import pytest
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        LLMRegistry.create("unknown_provider")


def test_registry_list_providers():
    providers = LLMRegistry.list_providers()
    assert "claude" in providers
    assert "openai_compat" in providers
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm/ -v
```

Expected: FAIL — modules not found.

- [ ] **Step 3: Write base.py**

```python
# core/llm/base.py
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    model: str
    tokens_used: int
    thinking: str | None = None


class LLMProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        ...

    @abstractmethod
    async def generate_with_thinking(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 16000,
        thinking_budget: int = 10000,
    ) -> LLMResponse:
        ...
```

- [ ] **Step 4: Write claude.py**

```python
# core/llm/claude.py
from __future__ import annotations

import anthropic

from core.llm.base import LLMProvider, LLMResponse


class ClaudeProvider(LLMProvider):
    provider_name = "claude"

    def __init__(self, api_key: str, model: str = "claude-opus-4-6"):
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)
        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )

    async def generate_with_thinking(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 16000,
        thinking_budget: int = 10000,
    ) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 1.0,  # Required for extended thinking
            "thinking": {"type": "enabled", "budget_tokens": thinking_budget},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)

        thinking_text = None
        content_text = ""
        for block in response.content:
            if block.type == "thinking":
                thinking_text = block.thinking
            elif block.type == "text":
                content_text = block.text

        return LLMResponse(
            content=content_text,
            model=response.model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            thinking=thinking_text,
        )
```

- [ ] **Step 5: Write registry.py**

```python
# core/llm/registry.py
from __future__ import annotations

from core.llm.base import LLMProvider
from core.llm.claude import ClaudeProvider
from core.llm.openai_compat import OpenAICompatProvider


_PROVIDERS: dict[str, type[LLMProvider]] = {
    "claude": ClaudeProvider,
    "openai_compat": OpenAICompatProvider,
    "ollama": OpenAICompatProvider,
    "vllm": OpenAICompatProvider,
    "lm_studio": OpenAICompatProvider,
}


class LLMRegistry:
    @staticmethod
    def create(provider: str, **kwargs) -> LLMProvider:
        cls = _PROVIDERS.get(provider)
        if cls is None:
            raise ValueError(f"Unknown LLM provider: {provider}")
        return cls(**kwargs)

    @staticmethod
    def list_providers() -> list[str]:
        return list(_PROVIDERS.keys())
```

- [ ] **Step 6: Write openai_compat.py stub** (needed by registry)

```python
# core/llm/openai_compat.py
from __future__ import annotations

from openai import AsyncOpenAI

from core.llm.base import LLMProvider, LLMResponse


class OpenAICompatProvider(LLMProvider):
    provider_name = "openai_compat"

    def __init__(
        self,
        api_key: str = "not-needed",
        base_url: str = "http://localhost:11434/v1",
        model: str = "llama3.1",
        **kwargs,
    ):
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = response.choices[0]
        tokens = (response.usage.total_tokens if response.usage else 0)
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model or self.model,
            tokens_used=tokens,
        )

    async def generate_with_thinking(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 16000,
        thinking_budget: int = 10000,
    ) -> LLMResponse:
        # OpenAI-compat providers don't support extended thinking
        # Fall back to standard generate with higher token budget
        return await self.generate(prompt, system, max_tokens, temperature=0.0)
```

- [ ] **Step 7: Write openai_compat tests**

```python
# tests/test_llm/test_openai_compat.py
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
    """OpenAI-compat providers fall back to standard generate for thinking."""
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
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_llm/ -v
```

Expected: All tests PASS (base, claude, openai_compat, registry).

- [ ] **Step 9: Commit**

```bash
git add core/llm/ tests/test_llm/
git commit -m "feat: LLM provider abstraction with Claude SDK and OpenAI-compat"
```

---

### Task 5: Secrets — AES-256-GCM Encryption

**Files:**
- Create: `core/secrets/base.py`
- Create: `core/secrets/encrypted.py`
- Test: `tests/test_secrets/test_encrypted.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_secrets/test_encrypted.py
import os
import pytest
from core.secrets.encrypted import EncryptedSecretsProvider


@pytest.fixture
def secrets_provider():
    # Generate a test master key (64 hex chars = 32 bytes)
    master_key = os.urandom(32).hex()
    return EncryptedSecretsProvider(master_key=master_key)


def test_encrypt_decrypt_roundtrip(secrets_provider):
    original = "sk-ant-api03-test-key-12345"
    encrypted, iv = secrets_provider.encrypt(original)
    decrypted = secrets_provider.decrypt(encrypted, iv)
    assert decrypted == original


def test_different_ivs_per_encryption(secrets_provider):
    key = "sk-ant-api03-test-key-12345"
    _, iv1 = secrets_provider.encrypt(key)
    _, iv2 = secrets_provider.encrypt(key)
    assert iv1 != iv2


def test_key_hint(secrets_provider):
    hint = secrets_provider.get_key_hint("sk-ant-api03-test-key-12345")
    assert hint == "...2345"


def test_decrypt_with_wrong_key():
    provider1 = EncryptedSecretsProvider(master_key=os.urandom(32).hex())
    provider2 = EncryptedSecretsProvider(master_key=os.urandom(32).hex())
    encrypted, iv = provider1.encrypt("secret")
    with pytest.raises(Exception):
        provider2.decrypt(encrypted, iv)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_secrets/ -v
```

Expected: FAIL — modules not found.

- [ ] **Step 3: Write base.py**

```python
# core/secrets/base.py
from __future__ import annotations

from abc import ABC, abstractmethod


class SecretsProvider(ABC):
    @abstractmethod
    def encrypt(self, plaintext: str) -> tuple[bytes, bytes]:
        """Encrypt a secret. Returns (ciphertext, iv)."""
        ...

    @abstractmethod
    def decrypt(self, ciphertext: bytes, iv: bytes) -> str:
        """Decrypt a secret."""
        ...

    def get_key_hint(self, plaintext: str) -> str:
        """Return last 4 chars as a hint for display."""
        return f"...{plaintext[-4:]}" if len(plaintext) >= 4 else plaintext
```

- [ ] **Step 4: Write encrypted.py**

```python
# core/secrets/encrypted.py
from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.secrets.base import SecretsProvider


class EncryptedSecretsProvider(SecretsProvider):
    def __init__(self, master_key: str):
        # master_key is a 64-char hex string (32 bytes)
        self._key = bytes.fromhex(master_key)
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> tuple[bytes, bytes]:
        iv = os.urandom(12)  # 96-bit nonce for AES-GCM
        ciphertext = self._aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
        return ciphertext, iv

    def decrypt(self, ciphertext: bytes, iv: bytes) -> str:
        plaintext_bytes = self._aesgcm.decrypt(iv, ciphertext, None)
        return plaintext_bytes.decode("utf-8")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_secrets/ -v
```

Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add core/secrets/ tests/test_secrets/
git commit -m "feat: AES-256-GCM secrets encryption for API key storage"
```

---

### Task 6: Storage — SQLite Local Fallback

**Files:**
- Create: `core/storage/base.py`
- Create: `core/storage/sqlite.py`
- Test: `tests/test_storage/test_sqlite.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storage/test_sqlite.py
import pytest
from uuid import uuid4
from core.storage.sqlite import SQLiteStorage
from core.models.patent import SearchResult, SearchStrategy


@pytest.fixture
async def storage(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = SQLiteStorage(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_save_and_get_project(storage):
    project_id = await storage.create_project(
        user_id=str(uuid4()),
        title="Test Invention",
        description="A system for testing",
    )
    assert project_id is not None
    project = await storage.get_project(project_id)
    assert project["title"] == "Test Invention"


@pytest.mark.asyncio
async def test_save_and_list_search_results(storage):
    user_id = str(uuid4())
    project_id = await storage.create_project(
        user_id=user_id,
        title="Test",
        description="Test",
    )
    sr = SearchResult(
        patent_id="US11234567",
        title="TEST PATENT",
        provider="patentsview",
        strategy=SearchStrategy.KEYWORD,
    )
    await storage.save_search_result(project_id, sr)
    results = await storage.list_search_results(project_id)
    assert len(results) == 1
    assert results[0]["patent_id"] == "US11234567"


@pytest.mark.asyncio
async def test_project_not_found(storage):
    project = await storage.get_project(str(uuid4()))
    assert project is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_storage/test_sqlite.py -v
```

Expected: FAIL — modules not found.

- [ ] **Step 3: Write base.py**

```python
# core/storage/base.py
from __future__ import annotations

from abc import ABC, abstractmethod

from core.models.patent import SearchResult


class StorageProvider(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

    @abstractmethod
    async def create_project(self, user_id: str, title: str, description: str, **kwargs) -> str:
        ...

    @abstractmethod
    async def get_project(self, project_id: str) -> dict | None:
        ...

    @abstractmethod
    async def save_search_result(self, project_id: str, result: SearchResult) -> str:
        ...

    @abstractmethod
    async def list_search_results(self, project_id: str) -> list[dict]:
        ...
```

- [ ] **Step 4: Write sqlite.py**

```python
# core/storage/sqlite.py
from __future__ import annotations

import json
from uuid import uuid4

import aiosqlite

from core.models.patent import SearchResult
from core.storage.base import StorageProvider


class SQLiteStorage(StorageProvider):
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS patent_projects (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                technical_field TEXT,
                filing_format TEXT,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS search_results (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES patent_projects(id),
                provider TEXT NOT NULL,
                patent_id TEXT NOT NULL,
                patent_title TEXT NOT NULL,
                patent_abstract TEXT,
                patent_date TEXT,
                inventors TEXT,
                assignees TEXT,
                cpc_codes TEXT,
                relevance_score REAL,
                relevance_notes TEXT,
                search_strategy TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def create_project(self, user_id: str, title: str, description: str, **kwargs) -> str:
        project_id = str(uuid4())
        await self._db.execute(
            "INSERT INTO patent_projects (id, user_id, title, description) VALUES (?, ?, ?, ?)",
            (project_id, user_id, title, description),
        )
        await self._db.commit()
        return project_id

    async def get_project(self, project_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM patent_projects WHERE id = ?", (project_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def save_search_result(self, project_id: str, result: SearchResult) -> str:
        result_id = str(result.id)
        await self._db.execute(
            """INSERT INTO search_results
               (id, project_id, provider, patent_id, patent_title, patent_abstract,
                patent_date, inventors, assignees, cpc_codes, relevance_score,
                relevance_notes, search_strategy)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result_id, project_id, result.provider, result.patent_id, result.title,
                result.abstract, str(result.patent_date) if result.patent_date else None,
                json.dumps([i.model_dump() for i in result.inventors]),
                json.dumps([a.model_dump() for a in result.assignees]),
                json.dumps(result.cpc_codes),
                result.relevance_score, result.relevance_notes, result.strategy.value,
            ),
        )
        await self._db.commit()
        return result_id

    async def list_search_results(self, project_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM search_results WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_storage/test_sqlite.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add core/storage/ tests/test_storage/
git commit -m "feat: storage abstraction with SQLite local fallback"
```

---

### Task 7: Database Schema & Docker Compose

**Files:**
- Create: `db/init.sql`
- Create: `docker-compose.yml`
- Create: `Dockerfile`

- [ ] **Step 1: Create db/init.sql**

This file is run by Supabase Postgres on first startup. Copy **lines 603-738** from the design spec (`docs/superpowers/specs/2026-03-24-memoriant-patent-platform-design.md`, Appendix A) verbatim into `db/init.sql`. This includes all 8 tables, RLS, and indexes.

Then add the missing RLS policies for all tables (the spec only shows one as an example):

```sql
-- Append these after the existing RLS ENABLE statements in the spec SQL:

CREATE POLICY "Users own data" ON public.profiles
    FOR ALL USING (auth.uid() = id);
CREATE POLICY "Users own data" ON public.patent_projects
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users own search results" ON public.search_results
    FOR ALL USING (
        project_id IN (SELECT id FROM public.patent_projects WHERE user_id = auth.uid())
    );
CREATE POLICY "Users own drafts" ON public.draft_applications
    FOR ALL USING (
        project_id IN (SELECT id FROM public.patent_projects WHERE user_id = auth.uid())
    );
CREATE POLICY "Users own pipeline runs" ON public.pipeline_runs
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users own file history" ON public.file_history
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users own configs" ON public.user_configs
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users own api keys" ON public.api_keys
    FOR ALL USING (auth.uid() = user_id);
```

Verify the SQL is valid:

```bash
# Quick syntax check (requires psql installed locally, or skip if not available)
psql -f db/init.sql --set ON_ERROR_STOP=1 "postgresql://localhost/template1" 2>&1 | head -5 || echo "Syntax check skipped — will validate on Docker startup"
```

- [ ] **Step 2: Create Dockerfile for patent-api**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY core/ core/
COPY api/ api/

RUN pip install --no-cache-dir ".[api]"

EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 3: Create docker-compose.yml**

Use the official Supabase self-hosted docker-compose as a base (from `github.com/supabase/supabase/docker`), then add patent-api and qdrant services. Key additions:

```yaml
  patent-api:
    build: .
    ports:
      - "8080:8080"
    env_file: .env
    depends_on:
      supabase-db:
        condition: service_healthy
      qdrant:
        condition: service_started
    networks:
      - internal
      - external
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    networks:
      - internal
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
```

To create the full docker-compose.yml:

```bash
# 1. Download the official Supabase self-hosted docker-compose as a starting point
curl -LO https://raw.githubusercontent.com/supabase/supabase/master/docker/docker-compose.yml
curl -LO https://raw.githubusercontent.com/supabase/supabase/master/docker/.env.example
# Rename their .env.example to avoid conflicts
mv .env.example .env.supabase.example

# 2. Append our services (patent-api, qdrant) to the downloaded docker-compose.yml
# 3. Add our networks (internal, external) to the networks section
# 4. Add volume mount for db/init.sql:
#    supabase-db:
#      volumes:
#        - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
# 5. Add security hardening to ALL services (user, read_only, cap_drop, security_opt)
# 6. Merge Supabase env vars into our .env.example
```

After merging, validate:

```bash
docker compose config > /dev/null && echo "docker-compose.yml is valid"
```

- [ ] **Step 4: Write health endpoint test (TDD — test first)**

```python
# tests/test_api/test_health.py
import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
```

- [ ] **Step 5: Run test to verify it fails**

```bash
pytest tests/test_api/test_health.py -v
```

Expected: FAIL — `api.main` has no `app` or no `/health` route.

- [ ] **Step 6: Write the FastAPI health stub**

```python
# api/main.py
from fastapi import FastAPI

app = FastAPI(
    title="Memoriant Patent Platform",
    version="0.1.0",
    description="Full-pipeline patent platform: idea to filing-ready draft",
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "services": {
            "api": "running",
        },
    }
```

- [ ] **Step 7: Run test to verify it passes**

```bash
pytest tests/test_api/test_health.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add db/ docker-compose.yml Dockerfile api/main.py tests/test_api/
git commit -m "feat: Docker Compose stack with Supabase, Qdrant, and FastAPI health endpoint"
```

---

### Task 8: Storage — Qdrant Vector Store

**Files:**
- Create: `core/storage/qdrant.py`
- Test: `tests/test_storage/test_qdrant.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storage/test_qdrant.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_storage/test_qdrant.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write qdrant.py**

```python
# core/storage/qdrant.py
from __future__ import annotations

from qdrant_client import AsyncQdrantClient, models


COLLECTION_NAME = "patent_embeddings"


class QdrantStorage:
    def __init__(self, host: str = "localhost", port: int = 6333):
        self._host = host
        self._port = port
        self._client = AsyncQdrantClient(host=host, port=port)

    async def initialize(self, dimensions: int = 1536) -> None:
        exists = await self._client.collection_exists(COLLECTION_NAME)
        if not exists:
            await self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=dimensions,
                    distance=models.Distance.COSINE,
                ),
            )

    async def upsert(self, point_id: str, vector: list[float], payload: dict) -> None:
        await self._client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(id=point_id, vector=vector, payload=payload),
            ],
        )

    async def search(
        self, query_vector: list[float], limit: int = 10, filters: dict | None = None,
    ) -> list[dict]:
        query_filter = None
        if filters:
            conditions = [
                models.FieldCondition(key=k, match=models.MatchValue(value=v))
                for k, v in filters.items()
            ]
            query_filter = models.Filter(must=conditions)

        results = await self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            query_filter=query_filter,
        )
        return [
            {"id": str(point.id), "score": point.score, **point.payload}
            for point in results.points
        ]

    async def close(self) -> None:
        await self._client.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_storage/test_qdrant.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add core/storage/qdrant.py tests/test_storage/test_qdrant.py
git commit -m "feat: Qdrant vector storage for patent embeddings"
```

---

### Task 9: Storage — Supabase Postgres (Stub)

**Files:**
- Create: `core/storage/supabase_pg.py`
- Create: `core/storage/registry.py`
- Test: `tests/test_storage/test_supabase_pg.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storage/test_supabase_pg.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.storage.supabase_pg import SupabaseStorage


@pytest.fixture
def supabase_storage():
    with patch("core.storage.supabase_pg.asyncpg") as mock_asyncpg:
        mock_pool = MagicMock()
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
        storage = SupabaseStorage(dsn="postgresql://test:test@localhost/test")
        storage._pool = mock_pool

        # Mock pool.acquire() as an async context manager
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])

        context_manager = AsyncMock()
        context_manager.__aenter__ = AsyncMock(return_value=mock_conn)
        context_manager.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = context_manager

        yield storage, mock_conn


@pytest.mark.asyncio
async def test_create_project(supabase_storage):
    storage, mock_conn = supabase_storage

    project_id = await storage.create_project(
        user_id="user-123", title="Test", description="Test invention"
    )
    # Returns a UUID string (generated internally, not from DB)
    assert len(project_id) == 36  # UUID format
    mock_conn.execute.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_storage/test_supabase_pg.py -v
```

- [ ] **Step 3: Write supabase_pg.py**

```python
# core/storage/supabase_pg.py
from __future__ import annotations

import json
from uuid import uuid4

import asyncpg

from core.models.patent import SearchResult
from core.storage.base import StorageProvider


class SupabaseStorage(StorageProvider):
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def create_project(self, user_id: str, title: str, description: str, **kwargs) -> str:
        project_id = str(uuid4())
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO patent_projects (id, user_id, title, description)
                   VALUES ($1, $2, $3, $4)""",
                project_id, user_id, title, description,
            )
        return project_id

    async def get_project(self, project_id: str) -> dict | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM patent_projects WHERE id = $1", project_id
            )
        return dict(row) if row else None

    async def save_search_result(self, project_id: str, result: SearchResult) -> str:
        result_id = str(result.id)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO search_results
                   (id, project_id, provider, patent_id, patent_title, patent_abstract,
                    patent_date, inventors, assignees, cpc_codes, relevance_score,
                    relevance_notes, search_strategy)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                result_id, project_id, result.provider, result.patent_id, result.title,
                result.abstract, result.patent_date,
                json.dumps([i.model_dump() for i in result.inventors]),
                json.dumps([a.model_dump() for a in result.assignees]),
                json.dumps(result.cpc_codes),
                result.relevance_score, result.relevance_notes, result.strategy.value,
            )
        return result_id

    async def list_search_results(self, project_id: str) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM search_results WHERE project_id = $1 ORDER BY created_at DESC",
                project_id,
            )
        return [dict(row) for row in rows]
```

- [ ] **Step 4: Write storage registry**

```python
# core/storage/registry.py
from __future__ import annotations

from core.storage.base import StorageProvider
from core.storage.sqlite import SQLiteStorage
from core.storage.supabase_pg import SupabaseStorage


class StorageRegistry:
    @staticmethod
    def create(backend: str, **kwargs) -> StorageProvider:
        if backend == "sqlite":
            return SQLiteStorage(db_path=kwargs.get("db_path", "~/.memoriant-patent/data.db"))
        elif backend == "supabase":
            return SupabaseStorage(dsn=kwargs["dsn"])
        else:
            raise ValueError(f"Unknown storage backend: {backend}")
```

- [ ] **Step 5: Run all storage tests**

```bash
pytest tests/test_storage/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add core/storage/ tests/test_storage/
git commit -m "feat: Supabase Postgres storage and storage registry"
```

---

### Task 10: Test Fixtures & Full Test Suite Run

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Create shared test fixtures**

```python
# tests/conftest.py
import os
import pytest


@pytest.fixture
def test_master_key():
    """A deterministic master key for test encryption."""
    return "a" * 64  # 32 bytes as hex


@pytest.fixture
def env_with_defaults(monkeypatch):
    """Set minimal environment variables for testing."""
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ENCRYPTION_MASTER_KEY", "a" * 64)
```

- [ ] **Step 2: Run the full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests PASS. Count should be ~20+ tests across models, LLM, storage, secrets, and API.

- [ ] **Step 3: Run with coverage**

```bash
pytest tests/ --cov=core --cov=api --cov-report=term-missing
```

Expected: 80%+ coverage on core/models, reasonable coverage elsewhere.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "feat: test fixtures and full suite verification"
```

- [ ] **Step 5: Push all Phase 1 work**

```bash
git push origin main
```

---

## Phase 1 Completion Checklist

After all tasks are complete, verify:

- [ ] `pytest tests/ -v` — all tests pass
- [ ] `python -c "from core.models.patent import Patent; print('OK')"` — imports work
- [ ] `python -c "from core.llm.registry import LLMRegistry; print(LLMRegistry.list_providers())"` — registry works
- [ ] `python -c "from core.secrets.encrypted import EncryptedSecretsProvider; print('OK')"` — secrets work
- [ ] `.env.example` has all config options documented
- [ ] `docker compose config` — validates docker-compose.yml (run when Docker stack is ready to test on P50)
- [ ] All code committed and pushed to `github.com/NathanMaine/memoriant-patent-platform`
