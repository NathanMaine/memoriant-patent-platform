# Phase 2: Search & Analysis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build patent search providers (PatentsView, USPTO ODP, SerpAPI) with parallel aggregation, and all analysis modules (101, 102, 103, 112(a), 112(b), formalities) so users can search for prior art and get structured patentability analysis.

**Architecture:** Search providers implement a common `SearchProvider` interface registered via `SearchRegistry`. The aggregator runs enabled providers in parallel and deduplicates results. Analysis modules each take an invention description + search results and produce structured findings with MPEP/USC citations. All modules use the LLM abstraction from Phase 1.

**Tech Stack:** Python 3.11+, httpx (async HTTP), Pydantic v2, structlog, pytest + pytest-asyncio. Phase 1 core library as foundation.

**Requirements:** 100% test coverage. Structured logging in every module. Every function traceable in logs.

---

## File Structure

```
core/
├── search/
│   ├── __init__.py
│   ├── base.py                # Abstract SearchProvider interface
│   ├── patentsview.py         # PatentsView API provider (free)
│   ├── uspto_odp.py           # USPTO Open Data Portal provider (free)
│   ├── serpapi.py             # SerpAPI Google Patents provider (paid, opt-in)
│   ├── aggregator.py          # Parallel search + result deduplication
│   └── registry.py            # Search provider registration + factory
├── analysis/
│   ├── __init__.py
│   ├── base.py                # Abstract AnalysisModule interface + shared types
│   ├── prior_art.py           # Multi-strategy prior art comparison
│   ├── claims.py              # 35 USC 112(b) definiteness
│   ├── specification.py       # 35 USC 112(a) enablement + written description
│   ├── novelty.py             # 35 USC 102 novelty pre-screening
│   ├── obviousness.py         # 35 USC 103 obviousness pre-screening
│   ├── eligibility.py         # 35 USC 101 subject matter eligibility
│   └── formalities.py         # MPEP 608 formalities check
├── embedding/
│   ├── __init__.py
│   ├── base.py                # Abstract EmbeddingProvider interface
│   ├── openai_embed.py        # text-embedding-3-small via OpenAI API
│   ├── ollama_embed.py        # nomic-embed-text via Ollama
│   └── chunker.py             # Patent text chunking (abstract, claims, description)
tests/
├── test_search/
│   ├── __init__.py
│   ├── test_patentsview.py
│   ├── test_uspto_odp.py
│   ├── test_serpapi.py
│   ├── test_aggregator.py
│   └── test_registry.py
├── test_analysis/
│   ├── __init__.py
│   ├── test_prior_art.py
│   ├── test_claims.py
│   ├── test_specification.py
│   ├── test_novelty.py
│   ├── test_obviousness.py
│   ├── test_eligibility.py
│   └── test_formalities.py
├── test_embedding/
│   ├── __init__.py
│   ├── test_openai_embed.py
│   ├── test_ollama_embed.py
│   └── test_chunker.py
```

---

### Task 1: Search Provider — Base Interface & Registry

**Files:**
- Create: `core/search/__init__.py`, `core/search/base.py`, `core/search/registry.py`
- Create: `tests/test_search/__init__.py`, `tests/test_search/test_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_search/test_registry.py
import pytest
from core.search.base import SearchProvider, SearchQuery, SearchResponse
from core.search.registry import SearchRegistry


def test_search_query_creation():
    q = SearchQuery(query="wireless power transfer", strategies=["keyword"])
    assert q.query == "wireless power transfer"
    assert q.max_results == 50  # default


def test_search_response_creation():
    r = SearchResponse(results=[], provider="patentsview", duration_ms=100)
    assert r.provider == "patentsview"
    assert len(r.results) == 0


def test_search_provider_is_abstract():
    with pytest.raises(TypeError):
        SearchProvider()


def test_registry_list_providers():
    providers = SearchRegistry.list_providers()
    assert "patentsview" in providers


def test_registry_get_enabled():
    enabled = SearchRegistry.get_enabled(
        patentsview_enabled=True, uspto_odp_enabled=True, serpapi_enabled=False
    )
    assert "patentsview" in [p.provider_name for p in enabled]
    assert "serpapi" not in [p.provider_name for p in enabled]


def test_registry_unknown_provider():
    with pytest.raises(ValueError):
        SearchRegistry.create("nonexistent")
```

- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement base.py**

```python
# core/search/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from core.models.patent import SearchResult, SearchStrategy
import structlog

logger = structlog.get_logger(__name__)


class SearchQuery(BaseModel):
    query: str
    strategies: list[str] = Field(default_factory=lambda: ["keyword"])
    date_range: dict | None = None  # {"start": "2020-01-01", "end": "2025-12-31"}
    cpc_codes: list[str] = Field(default_factory=list)
    inventors: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    max_results: int = 50


class SearchResponse(BaseModel):
    results: list[SearchResult]
    provider: str
    duration_ms: int
    total_hits: int = 0
    error: str | None = None


class SearchProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def search(self, query: SearchQuery) -> SearchResponse:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...
```

- [ ] **Step 4: Implement registry.py** (initially with just patentsview placeholder)

```python
# core/search/registry.py
from __future__ import annotations
import structlog
from core.search.base import SearchProvider

logger = structlog.get_logger(__name__)

_PROVIDERS: dict[str, type[SearchProvider]] = {}


def register_provider(name: str, cls: type[SearchProvider]):
    _PROVIDERS[name] = cls


class SearchRegistry:
    @staticmethod
    def create(name: str, **kwargs) -> SearchProvider:
        cls = _PROVIDERS.get(name)
        if cls is None:
            raise ValueError(f"Unknown search provider: {name}")
        logger.info("search.registry.create", provider=name)
        return cls(**kwargs)

    @staticmethod
    def list_providers() -> list[str]:
        return list(_PROVIDERS.keys())

    @staticmethod
    def get_enabled(
        patentsview_enabled: bool = True,
        uspto_odp_enabled: bool = True,
        serpapi_enabled: bool = False,
        **kwargs,
    ) -> list[SearchProvider]:
        enabled = []
        if patentsview_enabled and "patentsview" in _PROVIDERS:
            enabled.append(SearchRegistry.create("patentsview", **kwargs))
        if uspto_odp_enabled and "uspto_odp" in _PROVIDERS:
            enabled.append(SearchRegistry.create("uspto_odp", **kwargs))
        if serpapi_enabled and "serpapi" in _PROVIDERS:
            enabled.append(SearchRegistry.create("serpapi", **kwargs))
        return enabled
```

Note: Providers register themselves when imported. Each provider module calls `register_provider()` at module level.

- [ ] **Step 5: Run tests — verify PASS**
- [ ] **Step 6: Verify 100% coverage on new files**
- [ ] **Step 7: Commit**

```bash
git add core/search/ tests/test_search/ && git commit -m "feat: search provider base interface and registry"
```

---

### Task 2: PatentsView Search Provider

**Files:**
- Create: `core/search/patentsview.py`
- Create: `tests/test_search/test_patentsview.py`

PatentsView API: `POST https://search.patentsview.org/api/v1/patent/` with `X-Api-Key` header. Supports `_text_any`, `_text_all`, `_text_phrase`, `_and`, `_or`, `_not`, `_eq`, `_gte`, `_lte`, `_begins`, `_contains` operators.

- [ ] **Step 1: Write failing tests** — mock httpx responses for keyword search, CPC search, inventor search, date range, error handling (rate limit 429, invalid key 403, server error 500), empty results
- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement patentsview.py** — async httpx client, builds PatentsView query JSON from SearchQuery, parses response into SearchResult list, handles all error codes, includes structlog logging for every API call
- [ ] **Step 4: Register provider** — add `register_provider("patentsview", PatentsViewProvider)` at module level
- [ ] **Step 5: Run tests — verify PASS**
- [ ] **Step 6: 100% coverage check**
- [ ] **Step 7: Commit**

```bash
git commit -m "feat: PatentsView search provider with keyword, CPC, inventor, date range"
```

---

### Task 3: USPTO Open Data Portal Search Provider

**Files:**
- Create: `core/search/uspto_odp.py`
- Create: `tests/test_search/test_uspto_odp.py`

USPTO ODP API: REST API for patent applications and grants. Free, no API key required.

- [ ] **Step 1: Write failing tests** — mock httpx responses for keyword search, error handling, empty results
- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement uspto_odp.py** — async httpx client, query building, response parsing, error handling, structlog logging
- [ ] **Step 4: Register provider**
- [ ] **Step 5: Run tests — verify PASS**
- [ ] **Step 6: 100% coverage check**
- [ ] **Step 7: Commit**

```bash
git commit -m "feat: USPTO Open Data Portal search provider"
```

---

### Task 4: SerpAPI Google Patents Provider (Paid, Opt-in)

**Files:**
- Create: `core/search/serpapi.py`
- Create: `tests/test_search/test_serpapi.py`

SerpAPI: `GET https://serpapi.com/search?engine=google_patents&q=...&api_key=...`

- [ ] **Step 1: Write failing tests** — mock httpx responses, test that provider requires api_key, test opt-in behavior (not enabled by default)
- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement serpapi.py** — requires `api_key` param, raises if not provided, async httpx, response parsing, structlog logging
- [ ] **Step 4: Register provider**
- [ ] **Step 5: Run tests — verify PASS**
- [ ] **Step 6: 100% coverage check**
- [ ] **Step 7: Commit**

```bash
git commit -m "feat: SerpAPI Google Patents provider (paid, opt-in)"
```

---

### Task 5: Search Aggregator (Parallel Execution)

**Files:**
- Create: `core/search/aggregator.py`
- Create: `tests/test_search/test_aggregator.py`

- [ ] **Step 1: Write failing tests** — test parallel execution of 2 providers, test result deduplication (same patent_id from different providers), test single provider failure doesn't kill entire search, test empty results, test merge ordering (by relevance then date)
- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement aggregator.py** — uses `asyncio.gather()` with `return_exceptions=True` to run providers in parallel, deduplicates by patent_id (keeps highest relevance), merges and sorts results, logs per-provider timing and errors
- [ ] **Step 4: Run tests — verify PASS**
- [ ] **Step 5: 100% coverage check**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat: search aggregator with parallel execution and deduplication"
```

---

### Task 6: Analysis — Base Interface & Prior Art

**Files:**
- Create: `core/analysis/__init__.py`, `core/analysis/base.py`, `core/analysis/prior_art.py`
- Create: `tests/test_analysis/__init__.py`, `tests/test_analysis/test_prior_art.py`

- [ ] **Step 1: Write failing tests** — test AnalysisFinding model, test AnalysisResult model with severity levels, test prior_art module takes invention description + search results and returns structured comparison
- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement base.py** — `AnalysisFinding` (Pydantic: prior_art_id, overlap, distinguishing_features, severity), `AnalysisResult` (status: clear/caution/conflict, findings list, recommendation), abstract `AnalysisModule` with `analyze()` method
- [ ] **Step 4: Implement prior_art.py** — takes invention description + list of SearchResults, uses LLM to compare each result against invention, produces AnalysisResult with per-patent findings
- [ ] **Step 5: Run tests — verify PASS**
- [ ] **Step 6: 100% coverage check**
- [ ] **Step 7: Commit**

```bash
git commit -m "feat: analysis base interface and prior art comparison module"
```

---

### Task 7: Analysis — Novelty (102) & Obviousness (103)

**Files:**
- Create: `core/analysis/novelty.py`, `core/analysis/obviousness.py`
- Create: `tests/test_analysis/test_novelty.py`, `tests/test_analysis/test_obviousness.py`

- [ ] **Step 1: Write failing tests** — test novelty checks if any single prior art anticipates all claim elements, test obviousness checks if combining 2-3 references makes invention obvious
- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement novelty.py** — uses LLM with system prompt explaining 35 USC 102, structured output for findings
- [ ] **Step 4: Implement obviousness.py** — uses LLM with system prompt explaining 35 USC 103 and Graham v. John Deere factors
- [ ] **Step 5: Run tests — verify PASS**
- [ ] **Step 6: 100% coverage check**
- [ ] **Step 7: Commit**

```bash
git commit -m "feat: novelty (102) and obviousness (103) analysis modules"
```

---

### Task 8: Analysis — Claims (112b), Specification (112a), Eligibility (101)

**Files:**
- Create: `core/analysis/claims.py`, `core/analysis/specification.py`, `core/analysis/eligibility.py`
- Create: `tests/test_analysis/test_claims.py`, `tests/test_analysis/test_specification.py`, `tests/test_analysis/test_eligibility.py`

- [ ] **Step 1: Write failing tests** — test claims checks for indefiniteness/antecedent basis, test specification checks for enablement + written description support, test eligibility checks for abstract idea + "significantly more"
- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement all three modules** — each uses LLM with statute-specific system prompts and produces structured AnalysisResult
- [ ] **Step 4: Run tests — verify PASS**
- [ ] **Step 5: 100% coverage check**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat: claims (112b), specification (112a), and eligibility (101) analysis"
```

---

### Task 9: Analysis — Formalities (MPEP 608)

**Files:**
- Create: `core/analysis/formalities.py`
- Create: `tests/test_analysis/test_formalities.py`

- [ ] **Step 1: Write failing tests** — test checks for abstract length (≤150 words), title length, claim numbering, reference numeral consistency, margin/font compliance notes
- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement formalities.py** — rule-based checks (no LLM needed for most), plus LLM for nuanced checks, produces AnalysisResult
- [ ] **Step 4: Run tests — verify PASS**
- [ ] **Step 5: 100% coverage check**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat: formalities analysis (MPEP 608)"
```

---

### Task 10: Embedding Pipeline

**Files:**
- Create: `core/embedding/__init__.py`, `core/embedding/base.py`, `core/embedding/openai_embed.py`, `core/embedding/ollama_embed.py`, `core/embedding/chunker.py`
- Create: `tests/test_embedding/__init__.py`, `tests/test_embedding/test_openai_embed.py`, `tests/test_embedding/test_ollama_embed.py`, `tests/test_embedding/test_chunker.py`

- [ ] **Step 1: Write failing tests** — test chunker splits abstract (single chunk), claims (per-claim), description (512 tokens with 64 overlap), test embedding providers return correct dimension vectors, test query vs document prefixes
- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement chunker.py** — `chunk_patent_text(text, chunk_type)` returns list of chunks with metadata
- [ ] **Step 4: Implement openai_embed.py** — uses OpenAI API with `input_type` parameter for query vs document
- [ ] **Step 5: Implement ollama_embed.py** — uses Ollama API with `search_query:` / `search_document:` prefixes
- [ ] **Step 6: Run tests — verify PASS**
- [ ] **Step 7: 100% coverage check**
- [ ] **Step 8: Commit**

```bash
git commit -m "feat: embedding pipeline with chunking and query/document prefixes"
```

---

### Task 11: Full Suite Verification & Push

- [ ] **Step 1: Run full test suite with coverage**

```bash
pytest tests/ --cov=core --cov=api --cov-report=term-missing
```

Expected: 100% coverage, all tests pass.

- [ ] **Step 2: Verify all imports**

```bash
python -c "from core.search.registry import SearchRegistry; print('Search:', SearchRegistry.list_providers())"
python -c "from core.search.aggregator import SearchAggregator; print('Aggregator: OK')"
python -c "from core.analysis.novelty import NoveltyAnalyzer; print('Novelty: OK')"
python -c "from core.embedding.chunker import chunk_patent_text; print('Chunker: OK')"
```

- [ ] **Step 3: Push**

```bash
git push origin main
```

---

## Phase 2 Completion Checklist

- [ ] PatentsView provider searches by keyword, CPC, inventor, assignee, date range
- [ ] USPTO ODP provider searches grants and applications
- [ ] SerpAPI provider works with API key (opt-in only)
- [ ] Aggregator runs providers in parallel, deduplicates results
- [ ] All 6 analysis modules produce structured findings with statute citations
- [ ] Formalities checks abstract length, claim numbering, reference numerals
- [ ] Embedding pipeline chunks patent text and generates vectors
- [ ] 100% test coverage
- [ ] Structured logging in every module
- [ ] All code pushed
