# Phase 3: Drafting & Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build patent application drafters (provisional, non-provisional, PCT), the pipeline orchestrator with stage re-entry, FastAPI routes with auth and rate limiting, and DOCX/PDF export — completing the backend so the full pipeline works end-to-end.

**Architecture:** Drafting modules use the LLM abstraction to generate patent applications from invention descriptions + prior art analysis. The pipeline orchestrator chains all stages (describe → search → analyze → draft → review → export) with state persistence in Postgres for re-entry. FastAPI routes expose everything as a REST API with Supabase JWT auth and per-user rate limiting.

**Tech Stack:** Python 3.11+, FastAPI, python-docx, weasyprint, Pydantic v2, structlog, pytest + pytest-asyncio. Builds on Phase 1 (core) and Phase 2 (search + analysis).

**Requirements:** 100% test coverage. Structured logging in every module. TDD throughout.

---

## File Structure

```
core/
├── drafting/
│   ├── __init__.py
│   ├── base.py                # Abstract Drafter interface + shared prompts
│   ├── provisional.py         # USPTO provisional application
│   ├── nonprovisional.py      # USPTO non-provisional (utility)
│   └── pct.py                 # PCT international format
├── export/
│   ├── __init__.py
│   ├── docx_export.py         # python-docx with USPTO formatting
│   └── pdf_export.py          # weasyprint PDF generation
├── pipeline.py                # Stage-based orchestrator with re-entry
api/
├── main.py                    # FastAPI app (extend existing health stub)
├── routes/
│   ├── __init__.py
│   ├── search.py              # POST /search
│   ├── analyze.py             # POST /analyze
│   ├── draft.py               # POST /draft
│   ├── pipeline.py            # POST /pipeline
│   ├── config.py              # GET/PUT /config
│   └── health.py              # GET /health (extract from main.py)
├── middleware/
│   ├── __init__.py
│   ├── auth.py                # Supabase JWT verification
│   └── rate_limit.py          # Per-user, per-endpoint rate limiting
├── schemas/
│   ├── __init__.py
│   ├── requests.py            # API request Pydantic models
│   └── responses.py           # API response Pydantic models
└── deps.py                    # FastAPI dependencies (get_config, get_providers)
tests/
├── test_drafting/
│   ├── __init__.py
│   ├── test_provisional.py
│   ├── test_nonprovisional.py
│   └── test_pct.py
├── test_export/
│   ├── __init__.py
│   ├── test_docx_export.py
│   └── test_pdf_export.py
├── test_pipeline/
│   ├── __init__.py
│   └── test_pipeline.py
├── test_api/
│   ├── test_health.py         # (already exists)
│   ├── test_routes_search.py
│   ├── test_routes_analyze.py
│   ├── test_routes_draft.py
│   ├── test_routes_pipeline.py
│   ├── test_routes_config.py
│   ├── test_auth.py
│   └── test_rate_limit.py
```

---

### Task 1: Drafting — Base Interface + Provisional

**Files:**
- Create: `core/drafting/__init__.py`, `core/drafting/base.py`, `core/drafting/provisional.py`
- Create: `tests/test_drafting/__init__.py`, `tests/test_drafting/test_provisional.py`

- [ ] **Step 1: Write failing tests**

Test base Drafter is abstract. Test ProvisionalDrafter:
- Takes LLMProvider + invention description → generates DraftApplication with filing_format="provisional"
- Generated abstract ≤150 words
- Specification has background, summary, detailed_description, ≥1 embodiment
- Claims include ≥1 independent claim
- Filing checklist includes required items (cover sheet, fee, spec)
- Handles LLM error gracefully
- 12-15 tests

- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement base.py**

Abstract `Drafter` with `draft(invention_description, prior_art_results, preferences) -> DraftApplication`. Shared system prompts for patent drafting conventions.

- [ ] **Step 4: Implement provisional.py**

`ProvisionalDrafter(Drafter)`: LLM-based generation with system prompt explaining provisional requirements (detailed description, drawings, no formal claims required but recommended). Generates DraftApplication with filing checklist.

- [ ] **Step 5: Run — verify PASS**
- [ ] **Step 6: 100% coverage check**
- [ ] **Step 7: Commit:** `git commit -m "feat: drafting base interface and provisional application drafter"`

---

### Task 2: Drafting — Non-Provisional + PCT

**Files:**
- Create: `core/drafting/nonprovisional.py`, `core/drafting/pct.py`
- Create: `tests/test_drafting/test_nonprovisional.py`, `tests/test_drafting/test_pct.py`

- [ ] **Step 1: Write failing tests**

NonProvisionalDrafter tests:
- Generates multiple embodiments (≥ preferences.num_embodiments)
- Generates broad independent + narrow dependent claims (fallback strategy)
- Abstract exactly ≤150 words
- ADS data populated (inventor names, title, correspondence)
- Filing checklist includes: transmittal form, fee, spec, claims, abstract, drawings, ADS, oath
- 12-month deadline tracking: if provisional_filed_at is provided, calculates nonprovisional_deadline
- 12-15 tests

PCTDrafter tests:
- Sets filing_format="pct"
- Filing checklist includes PCT-specific items (request form, designation of states, priority claim)
- A4 paper note in specification
- 8-10 tests

- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement nonprovisional.py** — full utility application with multiple embodiments, layered claims, ADS generation
- [ ] **Step 4: Implement pct.py** — international format with PCT-specific requirements
- [ ] **Step 5: Run — verify PASS**
- [ ] **Step 6: 100% coverage check**
- [ ] **Step 7: Commit:** `git commit -m "feat: non-provisional and PCT patent application drafters"`

---

### Task 3: Export — DOCX + PDF

**Files:**
- Create: `core/export/__init__.py`, `core/export/docx_export.py`, `core/export/pdf_export.py`
- Create: `tests/test_export/__init__.py`, `tests/test_export/test_docx_export.py`, `tests/test_export/test_pdf_export.py`

- [ ] **Step 1: Write failing tests**

DOCX tests:
- `export_docx(draft: DraftApplication) -> bytes` returns valid DOCX bytes
- Title page present
- Abstract on separate page, ≤150 words
- Claims on separate page
- Specification sections in order (background, summary, detailed_description)
- Font is Times New Roman 12pt
- Double-spaced
- Includes filing disclaimer text
- 10-12 tests

PDF tests:
- `export_pdf(draft: DraftApplication) -> bytes` returns valid PDF bytes
- Contains title, abstract, claims
- 8-10 tests

- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement docx_export.py** — uses python-docx, creates Document with USPTO formatting (letter size, margins, fonts, spacing, page breaks between sections)
- [ ] **Step 4: Implement pdf_export.py** — generates HTML from DraftApplication, renders to PDF via weasyprint with USPTO-compliant CSS
- [ ] **Step 5: Run — verify PASS**
- [ ] **Step 6: 100% coverage check**
- [ ] **Step 7: Commit:** `git commit -m "feat: DOCX and PDF export with USPTO formatting"`

---

### Task 4: Pipeline Orchestrator

**Files:**
- Create: `core/pipeline.py`
- Create: `tests/test_pipeline/__init__.py`, `tests/test_pipeline/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Pipeline tests (mock all dependencies — LLM, search, analysis, drafting, export, storage):
- Full run: describe → search → analyze → draft → review → export → complete
- Stage tracking: stages_completed updates after each stage
- Re-entry: resume from "analyze" skips describe+search
- Prior art gate: CONFLICT status pauses pipeline, returns gate_blocked status
- Prior art gate override: user_override=True proceeds despite conflicts
- Stage failure: marks stage as failed with error, allows retry
- Metrics tracking: api_calls, tokens_used, duration_ms per stage
- Empty search results: still proceeds (with warning)
- 15-20 tests

- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement pipeline.py**

`PatentPipeline` class:
- Constructor takes: LLMProvider, StorageProvider, SearchAggregator, list of AnalysisModules, Drafter, ExportService
- `run(invention_description, filing_format, project_id?, resume_from?) -> PipelineResult`
- Each stage: update pipeline_runs row, execute, log metrics, update stages_completed
- Prior art gate between analyze and draft
- `PipelineResult(BaseModel)`: project_id, stages_completed, draft_application, export_files, metrics, warnings

- [ ] **Step 4: Run — verify PASS**
- [ ] **Step 5: 100% coverage check**
- [ ] **Step 6: Commit:** `git commit -m "feat: pipeline orchestrator with stage re-entry and prior art gate"`

---

### Task 5: API Schemas + Dependencies

**Files:**
- Create: `api/schemas/__init__.py`, `api/schemas/requests.py`, `api/schemas/responses.py`
- Create: `api/deps.py`
- Create: `api/routes/__init__.py`
- Create: `api/middleware/__init__.py`

- [ ] **Step 1: Write failing tests** — test request/response models validate correctly, test dependency injection
- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement request models** (from spec Appendix E): SearchRequest, AnalyzeRequest, DraftRequest, PipelineRequest, ConfigUpdateRequest
- [ ] **Step 4: Implement response models**: SearchResponse, AnalyzeResponse, DraftResponse, PipelineStartResponse, ConfigResponse, HealthResponse
- [ ] **Step 5: Implement deps.py**: `get_llm_provider()`, `get_storage()`, `get_search_registry()`, `get_user_id()` dependency functions
- [ ] **Step 6: Run — verify PASS**
- [ ] **Step 7: 100% coverage check**
- [ ] **Step 8: Commit:** `git commit -m "feat: API schemas and dependency injection"`

---

### Task 6: Auth Middleware (Supabase JWT)

**Files:**
- Create: `api/middleware/auth.py`
- Create: `tests/test_api/test_auth.py`

- [ ] **Step 1: Write failing tests**

- Valid JWT → extracts user_id, sets request.state.user_id
- Missing Authorization header → 401
- Invalid JWT (bad signature) → 401
- Expired JWT → 401
- Malformed header (not "Bearer <token>") → 401
- Health endpoint excluded from auth
- 8-10 tests

- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement auth.py** — FastAPI middleware that decodes Supabase JWT using JWT_SECRET from env, extracts `sub` claim as user_id
- [ ] **Step 4: Run — verify PASS**
- [ ] **Step 5: 100% coverage check**
- [ ] **Step 6: Commit:** `git commit -m "feat: Supabase JWT auth middleware"`

---

### Task 7: Rate Limiting Middleware

**Files:**
- Create: `api/middleware/rate_limit.py`
- Create: `tests/test_api/test_rate_limit.py`

- [ ] **Step 1: Write failing tests**

- Under limit → request passes
- At limit → 429 with Retry-After header
- Different users have separate limits
- Different endpoints have different limits (search=30/min, draft=5/min)
- Limits reset after window expires
- Health endpoint exempt
- 10-12 tests

- [ ] **Step 2: Run — verify FAIL**
- [ ] **Step 3: Implement rate_limit.py** — in-memory dict of {user_id+endpoint: [timestamps]}, configurable per-endpoint limits from env vars
- [ ] **Step 4: Run — verify PASS**
- [ ] **Step 5: 100% coverage check**
- [ ] **Step 6: Commit:** `git commit -m "feat: per-user per-endpoint rate limiting middleware"`

---

### Task 8: API Routes (Search, Analyze, Draft, Pipeline, Config)

**Files:**
- Create: `api/routes/search.py`, `api/routes/analyze.py`, `api/routes/draft.py`, `api/routes/pipeline.py`, `api/routes/config.py`, `api/routes/health.py`
- Modify: `api/main.py` — include all routers, add middleware
- Create: `tests/test_api/test_routes_search.py`, `tests/test_api/test_routes_analyze.py`, `tests/test_api/test_routes_draft.py`, `tests/test_api/test_routes_pipeline.py`, `tests/test_api/test_routes_config.py`

- [ ] **Step 1: Write failing tests** — for each route, test: success case, validation error (bad request body), auth required (no token → 401). Use httpx AsyncClient with ASGITransport. Mock all backend dependencies.

- [ ] **Step 2: Run — verify FAIL**

- [ ] **Step 3: Implement all route files** — each route file defines a FastAPI APIRouter, uses dependency injection for LLM/storage/search, calls core library functions, returns Pydantic response models

- [ ] **Step 4: Update api/main.py** — include all routers, add auth + rate limit middleware, extract health to its own route file

- [ ] **Step 5: Run — verify PASS**
- [ ] **Step 6: 100% coverage check on all api/ files**
- [ ] **Step 7: Commit:** `git commit -m "feat: all API routes with auth and rate limiting"`

---

### Task 9: Full Suite Verification + Push

- [ ] **Step 1: Run full test suite with coverage**

```bash
pytest tests/ --cov=core --cov=api --cov-report=term-missing
```

Expected: 100% coverage, all tests pass.

- [ ] **Step 2: Verify end-to-end imports**

```bash
python -c "from core.drafting.provisional import ProvisionalDrafter; print('Drafting: OK')"
python -c "from core.pipeline import PatentPipeline; print('Pipeline: OK')"
python -c "from core.export.docx_export import export_docx; print('Export: OK')"
python -c "from api.middleware.auth import AuthMiddleware; print('Auth: OK')"
```

- [ ] **Step 3: Push**

```bash
git push origin main
```

---

## Phase 3 Completion Checklist

- [ ] Provisional drafter generates complete application from invention description
- [ ] Non-provisional drafter generates multiple embodiments + layered claims + ADS
- [ ] PCT drafter generates international format
- [ ] DOCX export with USPTO formatting (margins, fonts, spacing, page breaks)
- [ ] PDF export as visual reference
- [ ] Pipeline runs full cycle: describe → search → analyze → draft → review → export
- [ ] Pipeline supports re-entry from any stage
- [ ] Prior art gate warns on conflicts, allows override
- [ ] All API routes work: /search, /analyze, /draft, /pipeline, /config, /health
- [ ] Supabase JWT auth on all protected routes
- [ ] Per-user rate limiting with configurable limits
- [ ] 100% test coverage
- [ ] Structured logging in every module
- [ ] All code pushed
