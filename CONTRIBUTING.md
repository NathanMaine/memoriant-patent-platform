# Contributing to Memoriant Patent Platform

**Owner:** Nathan Maine

Thank you for contributing. Please read this guide fully before opening a pull request.

---

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Running Tests](#running-tests)
3. [Coverage Requirement](#coverage-requirement)
4. [Structured Logging Requirement](#structured-logging-requirement)
5. [Code Style](#code-style)
6. [Extending the Platform](#extending-the-platform)
   - [Adding a Search Provider](#adding-a-search-provider)
   - [Adding an Analysis Module](#adding-an-analysis-module)
   - [Adding a Claude Code Skill](#adding-a-claude-code-skill)
7. [Pull Request Process](#pull-request-process)

---

## Development Environment Setup

```bash
# 1. Clone the repository
git clone https://github.com/NathanMaine/memoriant-patent-platform.git
cd memoriant-patent-platform

# 2. Create and activate a virtual environment (Python 3.11+)
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# 3. Install all dependencies (core + api + dev extras)
pip install -e ".[dev]"

# 4. Copy environment template and fill in your values
cp .env.example .env

# 5. Start backing services (Supabase + Qdrant) via Docker Compose
docker compose up -d supabase qdrant

# 6. (Optional) Start the full stack
docker compose up -d
```

For the React frontend:

```bash
cd web
npm install
npm run dev        # http://localhost:5173
```

---

## Running Tests

Always run the full test suite from the repo root:

```bash
pytest tests/ --cov=core --cov=api --cov-report=term-missing
```

To generate an HTML coverage report:

```bash
pytest tests/ --cov=core --cov=api --cov-report=html
open htmlcov/index.html
```

To run a single test file during development:

```bash
pytest tests/test_models.py -v
```

---

## Coverage Requirement

**100% test coverage is required. No exceptions.**

PRs that drop coverage below 100% will not be merged. The CI pipeline enforces this with:

```bash
pytest tests/ --cov=core --cov=api --cov-report=term-missing --cov-fail-under=100
```

If you add a new module, you must add corresponding tests that exercise every branch and line. Use `# pragma: no cover` only for genuinely unreachable defensive code, and only with a comment explaining why.

---

## Structured Logging Requirement

Every new module must use `structlog` for all log output. Never use `print()` or the standard `logging` module directly.

```python
import structlog

log = structlog.get_logger(__name__)

def my_function(patent_id: str) -> None:
    log.info("processing_patent", patent_id=patent_id)
    # ...
    log.debug("step_complete", patent_id=patent_id, step="prior_art_search")
```

Key rules:

- Logger names must match the module path (`__name__`).
- Log entries must include all relevant context as keyword arguments (not string interpolation).
- Use structured fields that can be queried by log aggregators.
- Log levels: `debug` for trace-level detail, `info` for normal operations, `warning` for recoverable issues, `error` for failures that need attention.

---

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
# Lint
ruff check .

# Auto-fix
ruff check . --fix

# Format
ruff format .
```

Configuration lives in `pyproject.toml`. Key settings:

- **Line length:** 100 characters
- **Target Python version:** 3.11
- All ruff default rules plus `I` (isort), `UP` (pyupgrade), `N` (pep8-naming)

CI will reject PRs that fail `ruff check .` or `ruff format --check .`.

---

## Extending the Platform

### Adding a Search Provider

1. Create a new file in `core/search/providers/`, e.g., `core/search/providers/my_provider.py`.
2. Implement the `SearchProvider` interface defined in `core/search/base.py`:

```python
from core.search.base import SearchProvider, SearchQuery, SearchResult

class MyProvider(SearchProvider):
    name = "my_provider"

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        # Call the external API and return normalized SearchResult objects
        ...

    async def health_check(self) -> bool:
        # Return True if the provider is reachable
        ...
```

3. Register the provider in `core/search/registry.py` by adding it to `PROVIDER_REGISTRY`.
4. Add provider configuration (API keys, base URL) to `core/config.py` and `.env.example`.
5. Write tests in `tests/search/test_my_provider.py` with 100% coverage. Mock all external HTTP calls.
6. Update `CHANGELOG.md` under an appropriate `[Unreleased]` section.

### Adding an Analysis Module

1. Create a new file in `core/analysis/`, e.g., `core/analysis/my_analysis.py`.
2. Implement the `AnalysisModule` interface defined in `core/analysis/base.py`:

```python
from core.analysis.base import AnalysisModule, AnalysisInput, AnalysisResult

class MyAnalysis(AnalysisModule):
    name = "my_analysis"

    async def analyze(self, input: AnalysisInput) -> AnalysisResult:
        # Use self.llm to call the configured LLM provider
        # Return a structured AnalysisResult
        ...
```

3. Register the module in the pipeline orchestrator in `core/pipeline/orchestrator.py`.
4. Add the module name to the `PipelineStage` enum if it requires a distinct pipeline stage.
5. Write tests in `tests/analysis/test_my_analysis.py` with 100% coverage. Mock all LLM calls.
6. Update `CHANGELOG.md`.

### Adding a Claude Code Skill

1. Create a new YAML skill file in `skills/`, e.g., `skills/patent-my-skill.yml`.
2. Follow the structure of existing skills (see `skills/patent-search.yml` as a reference):

```yaml
name: patent-my-skill
description: One-line description of what this skill does
prompt: |
  You are a patent platform assistant. Your task is: ...

  Steps:
    1. ...
    2. ...
tools:
  - Bash
  - Read
  - Write
```

3. If the skill requires a new agent, add a corresponding file in `agents/`.
4. Document the skill in `README.md` under the Skills section.
5. Update `CHANGELOG.md`.

---

## Pull Request Process

1. **Create a branch** from `main` with a descriptive name:
   ```bash
   git checkout -b feat/my-feature
   # or
   git checkout -b fix/issue-description
   ```

2. **Write tests first.** All new functionality must be covered by tests before implementation. This is not optional.

3. **Implement the feature or fix.** Follow the code style and structured logging requirements above.

4. **Verify 100% coverage locally** before pushing:
   ```bash
   pytest tests/ --cov=core --cov=api --cov-report=term-missing --cov-fail-under=100
   ```

5. **Run the linter:**
   ```bash
   ruff check . && ruff format --check .
   ```

6. **Update `CHANGELOG.md`** under `[Unreleased]` with a concise description of your change.

7. **Submit a PR** against `main`. The PR description must include:
   - What changed and why
   - How to test it manually (if applicable)
   - Confirmation that coverage is 100%

8. PRs require approval from Nathan Maine before merging.

**PRs that drop coverage below 100%, fail linting, or lack structured logging in new modules will not be merged.**
