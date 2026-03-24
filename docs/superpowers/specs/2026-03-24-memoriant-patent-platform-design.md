# Memoriant Patent Platform — Design Specification

**Date:** 2026-03-24
**Author:** Nathan Maine
**Status:** Approved (pending implementation planning)
**Version:** 1.0

## Overview

A full-pipeline patent platform that takes inventors from idea to filing-ready draft. Built as a modular core library consumed by two frontends: a self-hosted web application (FastAPI + React) and Claude Code skills for power users. The platform supports US patent filings in provisional, non-provisional (utility), and PCT international formats.

**Owner:** Nathan Maine (NathanMaine on GitHub)
**Product:** Memoriant Patent Platform
**Repository:** `github.com/NathanMaine/memoriant-patent-platform`

### Design Principles

- **Modular core, multiple frontends** — one source of truth for patent logic, consumed by web API and Claude Code skills
- **Free by default, paid opt-in** — free patent search sources always on, paid sources require explicit user configuration
- **Model-agnostic** — Claude API (default, optimized for Opus 4.6 1M context), Ollama, vLLM, LM Studio, or any OpenAI-compatible endpoint
- **Self-hosted, distributable** — single `docker compose up` deploys everything, no cloud dependency
- **Research aid, not legal advice** — complements human patent expertise, includes disclaimers throughout
- **Clean architecture** — business logic independent of infrastructure, registry pattern for all providers

### User Workflow

```
Describe Invention → Prior Art Search → Analysis → Draft Application → Review → Export
```

Each stage is independently accessible. The pipeline supports re-entry at any stage (resume from where you left off if a stage fails or needs revision).

---

## Section 1: Project Structure & Core Library

### Repository Layout

```
memoriant-patent-platform/
├── core/                          # memoriant-patent-core (shared Python library)
│   ├── llm/                       # LLM provider abstraction
│   │   ├── base.py               # Abstract LLMProvider interface
│   │   ├── claude.py             # Anthropic SDK (native, full feature access)
│   │   ├── openai_compat.py      # Ollama, vLLM, LM Studio (OpenAI-compatible API)
│   │   └── registry.py           # Provider registration + configuration
│   ├── search/                    # Patent search providers
│   │   ├── base.py               # Abstract SearchProvider interface
│   │   ├── patentsview.py        # Free — US patents, 76M+ records (default on)
│   │   ├── uspto_odp.py          # Free — USPTO Open Data Portal (default on)
│   │   ├── serpapi.py            # Paid — Google Patents via SerpAPI (opt-in)
│   │   ├── aggregator.py         # Parallel search across providers + result deduplication
│   │   └── registry.py           # Provider config, opt-in management
│   ├── analysis/                  # Patent analysis pipeline
│   │   ├── prior_art.py          # Multi-strategy: keyword, CPC, citation, assignee
│   │   ├── claims.py             # 35 USC 112(b) definiteness analysis
│   │   ├── specification.py      # 35 USC 112(a) enablement + written description review
│   │   ├── novelty.py            # 35 USC 102 novelty pre-screening
│   │   ├── obviousness.py        # 35 USC 103 obviousness pre-screening
│   │   ├── eligibility.py        # 35 USC 101 subject matter eligibility check
│   │   └── formalities.py        # MPEP 608 formalities check
│   ├── drafting/                  # Patent application generation
│   │   ├── base.py               # Abstract drafter interface
│   │   ├── provisional.py        # USPTO provisional application
│   │   ├── nonprovisional.py     # USPTO non-provisional (utility)
│   │   └── pct.py                # PCT international format
│   ├── models/                    # Pydantic domain models
│   │   ├── patent.py             # Patent, Claim, SearchResult, Citation
│   │   ├── application.py        # DraftApplication, FilingFormat, Embodiment
│   │   └── config.py             # UserConfig (API keys, provider preferences)
│   ├── storage/                   # Storage abstraction
│   │   ├── base.py               # Abstract StorageProvider interface
│   │   ├── supabase_pg.py        # Postgres via Supabase (users, drafts, configs)
│   │   ├── supabase_files.py     # Supabase Storage (generated PDFs/DOCX)
│   │   ├── qdrant.py             # Vector store (patent embeddings, semantic search)
│   │   ├── pgvector.py           # Lightweight vector fallback (small-scale users)
│   │   └── sqlite.py             # Local fallback (Claude Code / no-Docker usage)
│   └── pipeline.py               # Stage-based orchestrator with re-entry support
├── api/                           # FastAPI web service
├── web/                           # React 18 + Vite frontend
├── skills/                        # Claude Code skills
├── agents/                        # Claude Code agents
├── tests/                         # Test suite
├── docker-compose.yml             # One-command deployment
├── .env.example                   # All configurable settings
├── pyproject.toml                 # Python package config
├── docs/                          # Documentation
└── LICENSE                        # MIT
```

### Architecture Layers (Clean Architecture)

The core library follows concentric layers where dependencies point inward:

- **Inner layer — Domain models** (`core/models/`): Patent, Claim, SearchResult, DraftApplication. Pure data structures, no external dependencies.
- **Middle layer — Use cases** (`core/analysis/`, `core/drafting/`, `core/search/`, `core/pipeline.py`): Business logic for patent workflows. Depends only on domain models and abstract interfaces.
- **Outer layer — Infrastructure** (`core/llm/`, `core/storage/`, `core/search/*.py` providers): Concrete implementations of LLM providers, storage backends, and search APIs. Depends on middle layer interfaces.
- **Delivery layer** (`api/`, `web/`, `skills/`): FastAPI routes, React frontend, Claude Code skills. Consumes the core library, never contains business logic.

### LLM Provider Abstraction

Two provider implementations, chosen based on Brain Trust feedback (Fahd Mirza — use official SDKs when available, not reimplemented interfaces):

**`claude.py`** — Uses `anthropic` Python SDK directly. Full access to:
- Extended thinking (essential for patent analysis)
- 1M context window (reading multiple full patent specifications)
- Native tool use
- Streaming responses

**`openai_compat.py`** — Handles any provider speaking the OpenAI API format:
- Ollama (`http://host:11434/v1/`)
- vLLM (`http://host:8000/v1/`)
- LM Studio (`http://host:1234/v1/`)
- Any other OpenAI-compatible endpoint

Default configuration (optimized for first runs):
```
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=<user's key>
CLAUDE_MODEL=claude-opus-4-6
CLAUDE_EXTENDED_THINKING=true
CLAUDE_MAX_TOKENS=128000
```

### Search Provider Registry

All search providers implement a common `SearchProvider` interface. The `aggregator.py` runs enabled providers in parallel and deduplicates results.

| Provider | Cost | Default | Data |
|----------|------|---------|------|
| PatentsView | Free (API key required) | On | 76M+ US patents, full metadata |
| USPTO Open Data Portal | Free | On | US patents + applications |
| SerpAPI (Google Patents) | Paid per query | Off — opt-in | International coverage |

Paid providers require explicit configuration via the Settings page or `.env`. Keys are encrypted at rest in Postgres (AES-256). No surprise costs.

### Prior Art Search Strategies

Based on Brain Trust feedback (Craige Thompson, IPWatchdog), the search module implements the USPTO Seven Step Prior Art Search Strategy:

1. Brainstorm keywords from invention description (including synonyms)
2. Look up keywords in US Patent Classification Index
3. Verify class/subclass relevancy via Classification Schedule
4. Read Classification Definitions, note "see also" references
5. Search by classification in full-text patent databases
6. Review claims, specifications, and drawings of found patents
7. Check all references cited in found patents (citation chain tracking)

Search types supported:
- Keyword search (title, abstract, full text) with synonym expansion
- CPC/USPC classification search
- Inventor and assignee search
- Citation chain tracking (forward + backward)
- Date range filtering
- Complex boolean combinations (AND, OR, NOT with nesting)

### Pipeline Orchestrator

`pipeline.py` chains the stages: idea → search → analyze → draft → review.

Key design decisions based on Brain Trust feedback (Hamel Husain):
- **Stage-based with independent logging** — each stage logs its own metrics
- **Re-entry support** — resume from any stage without restarting
- **Prior art gate** — warns before drafting if no search has been done or strong conflicts exist (user can override)
- **Outcome + process metrics** — tracks both result quality and operational metrics (API calls, latency, token usage)

---

## Section 2: API Layer & Infrastructure

### Docker Compose Stack

Single `docker compose up` deploys the entire platform:

```yaml
services:
  # Supabase self-hosted stack
  supabase-db:          # Postgres 15 + pgvector (internal network only)
  supabase-auth:        # GoTrue — email, OAuth, magic links, JWT
  supabase-storage:     # S3-compatible file storage (generated PDFs/DOCX)
  supabase-rest:        # PostgREST — auto-generated REST API
  supabase-realtime:    # WebSocket — pipeline progress streaming
  supabase-studio:      # Admin dashboard UI
  supabase-kong:        # API gateway

  # Patent platform
  patent-api:           # FastAPI backend
  patent-web:           # React 18 + Vite frontend
  qdrant:               # Vector search for patent embeddings

networks:
  internal:             # Postgres, Qdrant, Auth — not exposed to host
  external:             # API + Web frontend — exposed

# Security hardening (all containers):
# - user: "1000:1000" (non-root)
# - read_only: true (with tmpfs for /tmp)
# - cap_drop: ALL
# - no-new-privileges: true
```

### Why Supabase Self-Hosted

Replaces Firebase (which is being phased out from Memoriant). Self-hosted Supabase provides all features needed:
- Postgres database with pgvector (structured data + lightweight vector fallback)
- GoTrue auth (signup, login, OAuth, JWT — same flow as Firebase Auth)
- S3-compatible file storage (generated patent documents)
- Realtime WebSocket subscriptions (pipeline progress)
- Studio admin dashboard
- Row-level security
- No cloud dependency, no usage limits — storage is whatever disk you give it

Missing from self-hosted (cloud-only): Edge Functions, branching, point-in-time recovery, built-in email. None of these are needed — we use FastAPI for compute, git for branching, standard Postgres backups, and any SMTP provider for email.

### Primary Deployment Target

**ThinkPad P50** — 96 GB RAM, dedicated server role.

Resource requirements for the full stack: ~2-4 GB RAM. The P50 has headroom for 20+ instances.

The GPU (4 GB) is not needed — Supabase, Qdrant, FastAPI, and React are all CPU-only workloads. LLM inference runs on Claude API (default) or DGX Spark/P16 for local models.

### Vector Storage: Qdrant + pgvector Fallback

Based on Brain Trust feedback (Rost Glukhov — Vector Stores for RAG Comparison):

- **Qdrant** (primary) — Rust-based, Docker-native, excellent metadata filtering, handles 100K-10M+ vectors. Used for patent embeddings enabling semantic similarity search across patent abstracts, claims, and descriptions.
- **pgvector** (fallback) — for small-scale users who don't want to run Qdrant. Same `StorageProvider` interface, lower performance ceiling but zero additional infrastructure.
- **SQLite** (local fallback) — for Claude Code standalone usage without Docker.

### FastAPI Backend

```
api/
├── main.py                    # FastAPI app, CORS, startup/shutdown
├── routes/
│   ├── search.py              # POST /search — prior art search (all providers)
│   ├── analyze.py             # POST /analyze — claims, spec, formalities, novelty, obviousness
│   ├── draft.py               # POST /draft — generate application (3 formats)
│   ├── pipeline.py            # POST /pipeline — full end-to-end (progress via Supabase Realtime)
│   ├── config.py              # GET/PUT /config — provider settings, API key management
│   └── health.py              # GET /health — status + provider availability
├── middleware/
│   ├── auth.py                # Supabase JWT verification
│   └── rate_limit.py          # Per-user rate limiting (protects paid API quotas)
├── secrets/
│   ├── base.py                # Abstract secrets interface
│   ├── postgres.py            # Default: AES-256 encrypted API keys in Postgres
│   └── vault.py               # Optional: OpenBao/Vault for enterprise (audit trails, rotation)
└── schemas/
    ├── requests.py            # API request models
    └── responses.py           # API response models
```

### Secrets Management

Two tiers based on Brain Trust feedback (Bright Coding — OpenBao):

- **Default:** API keys encrypted at rest in Postgres (AES-256). Never returned in plaintext after initial save. Sufficient for most users.
- **Advanced (opt-in):** OpenBao/Vault integration for enterprise users needing audit trails, auto-rotation, and dynamic secrets with TTL. Configured via environment variable `SECRETS_BACKEND=vault`.

### Real-Time Pipeline Progress

Uses Supabase Realtime instead of custom WebSocket implementation (based on Brain Trust feedback). Pipeline stages write to a `pipeline_runs` table in Postgres; the React frontend subscribes via Supabase JS client and displays live progress updates.

### React Frontend

```
web/src/
├── pages/
│   ├── Dashboard.tsx          # Recent searches, drafts in progress, filing deadlines
│   ├── NewPatent.tsx          # Wizard: describe → search → analyze → draft → review → export
│   ├── SearchResults.tsx      # Prior art results + comparison table
│   ├── DraftEditor.tsx        # Review/edit generated application
│   └── Settings.tsx           # Provider config, API keys, model selection
├── components/
│   ├── PipelineProgress.tsx   # Supabase Realtime subscription — live stage updates
│   ├── PatentCard.tsx         # Search result display with relevance scoring
│   ├── ClaimsTree.tsx         # Hierarchical claims viewer (independent + dependent)
│   ├── ClaimChart.tsx         # Side-by-side claim vs prior art mapping
│   ├── ComparisonTable.tsx    # Invention vs prior art feature comparison
│   ├── FileHistory.tsx        # Audit trail of all actions on a patent project
│   └── ExaminerStats.tsx      # USPTO examiner allowance rate lookup
├── hooks/
│   ├── usePipeline.ts         # Supabase Realtime hook for pipeline progress
│   └── usePatentSearch.ts     # Search query + result management
└── services/
    ├── api.ts                 # FastAPI client (typed, matches API schemas)
    └── supabase.ts            # Supabase client (auth, realtime, storage)
```

Stack: React 18 + Vite + TypeScript (matches Memoriant's existing stack).

### NewPatent Wizard Flow

1. **Describe** — user enters invention idea, key features, target technical field
2. **Search** — system runs parallel prior art search across enabled providers, streams results in real time
3. **Analyze** — prior art comparison table, novelty assessment, potential conflicts flagged with specific claim overlap
4. **Draft** — user picks filing format (provisional / non-provisional / PCT), system generates complete application
5. **Review** — AI-assisted review (101 eligibility, 102 novelty, 103 obviousness, 112 claims/spec, formalities), user edits in-place
6. **Export** — download as DOCX/PDF, ready for attorney review or filing

Prior art gate lives between steps 3 and 4: if analysis shows strong conflicts, the UI shows a warning before allowing draft generation. User can override but it's documented in the file history.

---

## Section 3: Claude Code Skills & Agents

### Skills

Six skills, each with test cases for measuring effectiveness across models:

```
skills/
├── patent-search/
│   ├── skill.md               # Multi-strategy search (USPTO 7-step method)
│   └── test_cases.md          # Search accuracy evaluation
├── patent-draft/
│   ├── skill.md               # Generate applications (provisional/non-provisional/PCT)
│   └── test_cases.md          # Drafting quality tests
├── patent-review/
│   ├── skill.md               # Full review: 101, 102, 103, 112(a), 112(b), formalities
│   └── test_cases.md          # Review accuracy tests
├── patent-diagrams/
│   ├── skill.md               # Patent-specific diagrams (delegates rendering to visual-explainer)
│   └── test_cases.md          # Diagram quality tests
├── patent-pipeline/
│   ├── skill.md               # End-to-end: idea → filing-ready draft
│   └── test_cases.md          # Pipeline completion tests
└── patent-config/
    └── skill.md               # Provider/API key configuration
```

### Skill Details

**patent-search** — Multi-strategy prior art search following USPTO 7-step methodology. Supports keyword, CPC classification, inventor, assignee, citation chain, date range, and complex boolean searches. Builds on PatentsView API documentation. Results formatted as comparison tables. Positions itself as research aid alongside human expertise.

**patent-draft** — Generates complete patent applications. Key capabilities from Brain Trust feedback (Craige Thompson):
- Multiple claim sets: broad independent claims + narrower dependent claims as fallback
- Multiple technical embodiments (not just one way to implement the invention)
- Proper Application Data Sheet (ADS) generation
- Filing checklists per format type
- 12-month provisional → non-provisional deadline tracking and warnings
- Abstract limited to 150 words per USPTO rules

**patent-review** — AI-assisted review against all major rejection types:

| Rejection Type | Statute | What It Checks |
|---------------|---------|---------------|
| Subject matter eligibility | 35 USC 101 | Abstract idea without "significantly more" |
| Novelty | 35 USC 102 | Prior art anticipating every claim element |
| Obviousness | 35 USC 103 | Combining 2-3 prior art references |
| Written description | 35 USC 112(a) | Spec supports what's claimed |
| Enablement | 35 USC 112(a) | Skilled person can make/use from description |
| Indefiniteness | 35 USC 112(b) | All claim terms clear and definite |
| Formalities | MPEP 608 | Margins, font, reference numerals, abstract length |

Produces actionable feedback with specific citations to MPEP/USC sections.

**patent-diagrams** — Patent-specific diagram generation. Delegates rendering to visual-explainer plugin (Option C integration). Adds patent domain layer:
- Reference numbering consistent with claim elements
- System architecture diagrams
- Master flow chart + detailed subroutine flow charts
- Two output modes: informal (provisional — relaxed formatting) and formal (non-provisional — USPTO drawing rules: consistent arrow lengths, box widths, margins, font sizes)
- Content determination based on invention type (software → flow charts, hardware → component views, method → process diagrams)

**patent-pipeline** — Full end-to-end orchestration. Describe your idea, get a complete filing-ready draft. Runs all stages with progress updates, pauses at prior art gate if conflicts found. Outputs: final application + prior art report + review notes + diagrams.

**patent-config** — Configure the platform: set LLM provider (Claude/Ollama/vLLM/LM Studio), add paid search provider API keys, point at self-hosted API endpoint or run standalone. Stores config in `~/.memoriant-patent/config.yaml`.

### Two Operating Modes

**Mode 1: API-connected** (P50 running Docker stack)
- Skills call FastAPI endpoints
- Full features: search history, saved drafts, Qdrant semantic search, auth, Supabase Realtime
- Same data whether using Claude Code or web UI

**Mode 2: Standalone** (no Docker, just Claude Code)
- Skills use core library directly with SQLite fallback
- PatentsView + USPTO search via curl (free, no infrastructure)
- LLM calls go to configured provider (Claude API, remote Ollama, etc.)
- Good for quick searches or when P50 is off

### Agents

Four agents with clear, non-overlapping responsibilities:

```
agents/
├── prior-art-searcher.md      # Autonomous multi-strategy search (USPTO 7-step)
├── patent-drafter.md          # Multi-embodiment drafting with iterative refinement
├── patent-reviewer.md         # Full rejection pre-screening (101-112 + formalities)
└── patent-illustrator.md      # Diagram generation via visual-explainer
```

**prior-art-searcher** — Implements the full USPTO 7-step search strategy autonomously. Starts with keyword brainstorming, identifies CPC classifications, runs parallel searches, tracks citation chains, and produces a structured prior art report with relevance scoring. Follows the hybrid AI + manual approach: presents findings for human review, suggests areas for deeper manual investigation.

**patent-drafter** — Takes invention description + prior art analysis as input. Generates complete application with multiple embodiments, layered claim sets (broad → narrow fallbacks), proper specification structure, and filing-specific formatting. Tracks the 12-month provisional deadline. Iterates on drafts based on user feedback.

**patent-reviewer** — Reviews draft applications against all major rejection types (101, 102, 103, 112(a), 112(b), formalities). Cross-references claims against the specification and prior art. Produces a structured review with specific MPEP/USC citations and suggested fixes. Flags the most likely examiner objections.

**patent-illustrator** — Determines required diagrams based on invention type and claims. Generates content with proper patent conventions (reference numerals, element labeling). Delegates rendering to visual-explainer for Mermaid diagrams, CSS Grid architecture layouts, and interactive flow charts. Supports informal (provisional) and formal (non-provisional) output modes.

### visual-explainer Integration (Option C)

visual-explainer (by Nico Bailon, MIT license) is used as the rendering engine. It is installed as a companion Claude Code plugin.

Separation of concerns:
- **Our patent-diagrams skill** decides what to draw (system architecture, flow charts, subroutine details), applies patent conventions (reference numerals, claim element labeling, USPTO formatting rules)
- **visual-explainer** renders it beautifully (Mermaid.js, Chart.js, CSS Grid, zoom/pan, light/dark themes, anti-slop guardrails)

This gives us high-quality, interactive patent diagrams without building our own rendering engine. Upstream updates to visual-explainer automatically improve our output quality.

---

## Section 4: Deployment & Distribution

### Docker Compose Deployment

```yaml
# docker-compose.yml — single command: docker compose up
services:
  # Supabase self-hosted (auth, database, storage, realtime)
  supabase-db:
    image: supabase/postgres:15
    networks: [internal]
    # pgvector extension enabled

  supabase-auth:
    image: supabase/gotrue
    networks: [internal]

  supabase-storage:
    image: supabase/storage-api
    networks: [internal]

  supabase-rest:
    image: postgrest/postgrest
    networks: [internal]

  supabase-realtime:
    image: supabase/realtime
    networks: [internal]

  supabase-studio:
    image: supabase/studio
    networks: [internal, external]

  supabase-kong:
    image: kong
    networks: [internal, external]

  # Patent platform
  patent-api:
    build: ./api
    networks: [internal, external]
    depends_on: [supabase-db, qdrant]

  patent-web:
    build: ./web
    networks: [external]
    depends_on: [patent-api]

  qdrant:
    image: qdrant/qdrant
    networks: [internal]

networks:
  internal:
    internal: true    # Not exposed to host
  external:           # Exposed
```

### Security Hardening

All containers run with:
- `user: "1000:1000"` — non-root
- `read_only: true` — immutable root filesystem (tmpfs for /tmp)
- `cap_drop: ALL` — drop all Linux capabilities
- `security_opt: no-new-privileges:true`
- Internal services (Postgres, Qdrant, Auth) on private network — not exposed to host

### Target Deployment Environments

| Environment | Stack | Use Case |
|-------------|-------|----------|
| **ThinkPad P50** (96 GB RAM) | Full Docker Compose | Primary instance — development + production |
| **DGX Spark** (128 GB, GB10) | Ollama/vLLM for local LLM serving | patent-api points here for AI inference |
| **Any Linux/Mac server** | Full Docker Compose | Self-hosted by other users |
| **Developer laptop** | Core library + SQLite | Claude Code skills only, no Docker needed |

### Configuration

```bash
# .env.example

# === Required ===
POSTGRES_PASSWORD=changeme
JWT_SECRET=changeme

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

# === Secrets Backend ===
# SECRETS_BACKEND=postgres  (default: AES-256 encrypted in Postgres)
# SECRETS_BACKEND=vault     (optional: OpenBao/Vault for enterprise)

# === Qdrant ===
QDRANT_HOST=qdrant
QDRANT_PORT=6333
```

### Distribution Model

Three ways users can adopt the platform:

1. **Full platform** — `git clone` + `docker compose up` → web UI + API + auth + vector search. Everything running in minutes.

2. **Core library only** — `pip install memoriant-patent-core` → import and use in their own Python projects. No Docker needed, SQLite storage.

3. **Claude Code skills only** — install the skills directory into Claude Code. Patent search, drafting, review, and diagrams available as slash commands. Works standalone with SQLite or connected to a running API instance.

### Documentation

```
docs/
├── QUICKSTART.md              # docker compose up and you're running
├── CONFIGURATION.md           # API keys, LLM providers, search providers
├── CLAUDE_CODE_SETUP.md       # Installing skills without Docker
├── API_REFERENCE.md           # Full API documentation
├── FILING_FORMATS.md          # Provisional vs non-provisional vs PCT guide
└── ARCHITECTURE.md            # System design for contributors
```

### Memoriant Integration Path

The patent platform runs standalone initially. Integration with Memoriant when ready:

- **Shared auth** — same Supabase instance, users with Memoriant accounts get patent access
- **Meeting → Patent pipeline** — meeting intelligence (Project Aurora Echo) feeds invention descriptions directly into the patent pipeline
- **Unified dashboard** — patent status appears as a module in the Memoriant dashboard
- **Timeline integration** — 12-month provisional deadlines appear in Memoriant's project timelines

---

## Brain Trust Expert Insights (Summary)

Key expert feedback that shaped this design:

| Expert | Insight | How It Shaped Design |
|--------|---------|---------------------|
| **Fahd Mirza** | Use official SDKs, not reimplemented interfaces | Claude gets native Anthropic SDK, not OpenAI-compat wrapper |
| **Rost Glukhov** | Clean architecture: business logic independent of infrastructure | Core library with concentric layers, delivery mechanisms as outer layer |
| **Rost Glukhov** | Qdrant for 100K+ vectors, pgvector for smaller scale | Qdrant primary, pgvector fallback for lightweight deployments |
| **Hamel Husain** | Segment errors by pipeline stage, use outcome + process metrics | Pipeline with stage-based logging, re-entry, and dual metrics |
| **Craige Thompson** | Multi-strategy search (keyword + classification + citation) | USPTO 7-step strategy in prior-art-searcher agent |
| **Craige Thompson** | Multiple embodiments + fallback claims are essential | patent-drafter generates broad → narrow claim layers |
| **Craige Thompson** | Provisional → non-provisional 12-month deadline is critical | Deadline tracking built into drafter + dashboard |
| **IPWatchdog** | Hybrid AI + manual search optimizes success | Platform positions as research aid, not legal advice replacement |
| **IPWatchdog** | Flow charts are worth 10x their weight in gold | Dedicated patent-diagrams skill + illustrator agent |
| **IPWatchdog** | All rejection types must be checked (101-112) | Review covers 101, 102, 103, 112(a), 112(b), formalities |
| **Bright Coding** | OpenBao for secrets, not homegrown encryption | Two-tier secrets: Postgres AES-256 default, Vault opt-in |
| **Bright Coding** | Docker security: non-root, read-only fs, capability drops | Hardened docker-compose.yml as default |
| **Bright Coding** | Use Supabase Realtime instead of custom WebSocket | Pipeline progress via Supabase Realtime subscriptions |
| **Nate B Jones** | Skills are versioned, mountable instruction packages | Skills designed as self-contained packages with test cases |

---

## Success Criteria

The platform is ready for initial use when:

1. `docker compose up` starts the full stack on the P50 without manual steps
2. A user can describe an invention and get prior art search results from PatentsView
3. The pipeline generates a complete provisional patent application from an invention description
4. Claims analysis identifies at least the most common rejection types (112(a), 112(b))
5. Patent diagrams render in the browser via visual-explainer
6. Claude Code skills work in standalone mode (no Docker) with SQLite fallback
7. All API keys are encrypted at rest, paid search providers are off by default
8. The platform clearly states it is a research aid, not legal advice

---

## Appendix A: Database Schema

### Core Tables

```sql
-- Users (managed by Supabase Auth / GoTrue)
-- Supabase creates auth.users automatically. We extend with:
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    role TEXT DEFAULT 'user',          -- 'user', 'admin' (v2 role-based access)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User provider configuration (LLM + search API keys)
CREATE TABLE public.user_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    llm_provider TEXT NOT NULL DEFAULT 'claude',        -- claude, ollama, vllm, lm_studio
    llm_endpoint TEXT,                                   -- URL for non-Claude providers
    llm_model TEXT DEFAULT 'claude-opus-4-6',
    extended_thinking BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Encrypted API keys (AES-256-GCM, key derived from ENCRYPTION_MASTER_KEY env var)
CREATE TABLE public.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,          -- anthropic, patentsview, serpapi, ollama, etc.
    encrypted_key BYTEA NOT NULL,    -- AES-256-GCM encrypted
    iv BYTEA NOT NULL,               -- Initialization vector
    key_hint TEXT,                    -- Last 4 chars for display (e.g., "...a3f2")
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

-- Patent projects (one per invention idea)
CREATE TABLE public.patent_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,        -- Invention description
    technical_field TEXT,
    filing_format TEXT,               -- provisional, nonprovisional, pct
    status TEXT DEFAULT 'draft',      -- draft, searching, analyzed, drafting, reviewing, complete
    provisional_filed_at TIMESTAMPTZ, -- When provisional was filed (for 12-month tracking)
    nonprovisional_deadline TIMESTAMPTZ, -- Auto-calculated: provisional_filed_at + 12 months
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Search results (cached per project)
CREATE TABLE public.search_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.patent_projects(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,           -- patentsview, uspto_odp, serpapi
    patent_id TEXT NOT NULL,          -- e.g., "US11234567"
    patent_title TEXT NOT NULL,
    patent_abstract TEXT,
    patent_date DATE,
    inventors JSONB,                  -- [{first: "John", last: "Smith"}]
    assignees JSONB,                  -- [{organization: "Google LLC"}]
    cpc_codes JSONB,                  -- ["G06F", "H04L"]
    relevance_score FLOAT,           -- 0.0-1.0, computed by analysis
    relevance_notes TEXT,
    search_strategy TEXT,             -- keyword, classification, citation, assignee
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Draft applications
CREATE TABLE public.draft_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.patent_projects(id) ON DELETE CASCADE,
    version INT NOT NULL DEFAULT 1,
    filing_format TEXT NOT NULL,      -- provisional, nonprovisional, pct
    title TEXT NOT NULL,
    abstract TEXT,                    -- Max 150 words
    specification JSONB NOT NULL,     -- {background, summary, detailed_description, embodiments[]}
    claims JSONB NOT NULL,            -- [{number, type: "independent"|"dependent", depends_on, text}]
    drawings_description TEXT,
    ads_data JSONB,                   -- Application Data Sheet fields
    review_notes JSONB,              -- [{type: "101"|"102"|"103"|"112a"|"112b"|"formalities", finding, severity, suggestion}]
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pipeline runs (Supabase Realtime subscribes to this)
CREATE TABLE public.pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.patent_projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    current_stage TEXT NOT NULL,      -- describe, search, analyze, draft, review, export, complete, failed
    stage_status TEXT NOT NULL,       -- pending, running, completed, failed, skipped
    stage_progress JSONB,            -- {message: "Searching PatentsView...", percent: 45}
    stages_completed JSONB DEFAULT '[]', -- ["describe", "search"] — for re-entry
    error_message TEXT,
    metrics JSONB,                   -- {api_calls: 12, tokens_used: 45000, duration_ms: 32000}
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- File history / audit trail
CREATE TABLE public.file_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.patent_projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    action TEXT NOT NULL,             -- created, searched, analyzed, drafted, reviewed, exported, edited
    details JSONB,                    -- Action-specific metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row-level security: users can only access their own data
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patent_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.draft_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.file_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

-- Policy: users see only their own rows
CREATE POLICY "Users own data" ON public.patent_projects
    FOR ALL USING (auth.uid() = user_id);
-- (Same pattern applied to all tables)

-- Performance indexes (composite, per Brain Trust review - Rost Glukhov)
CREATE INDEX idx_patent_projects_user ON patent_projects(user_id, updated_at DESC);
CREATE INDEX idx_search_results_project ON search_results(project_id, created_at DESC);
CREATE INDEX idx_draft_applications_project ON draft_applications(project_id, version DESC);
CREATE INDEX idx_pipeline_runs_project ON pipeline_runs(project_id, started_at DESC);
CREATE INDEX idx_pipeline_runs_user ON pipeline_runs(user_id, started_at DESC);
CREATE INDEX idx_file_history_project ON file_history(project_id, created_at DESC);
CREATE INDEX idx_patent_projects_status ON patent_projects(user_id, status);
CREATE INDEX idx_patent_projects_deadline ON patent_projects(nonprovisional_deadline)
    WHERE nonprovisional_deadline IS NOT NULL;
```

### Qdrant Collections

```python
# Patent embeddings for semantic similarity search
collection: "patent_embeddings"
vector_size: 1536          # text-embedding-3-small (OpenAI) or 768 for nomic-embed-text
distance: Cosine
payload_schema:
    patent_id: str         # "US11234567"
    project_id: str        # UUID of patent_project
    chunk_type: str        # "abstract", "claim", "description"
    chunk_index: int       # Position within document
    text: str              # Original text (for display)
    metadata: dict         # {date, assignee, cpc_codes}
```

---

## Appendix B: Embedding Model & Chunking

### Embedding Model

Default: **`text-embedding-3-small`** via OpenAI API (1536 dimensions, $0.02/1M tokens). Chosen for:
- Wide compatibility (available everywhere)
- Good balance of quality vs cost for patent text
- Same API works with local alternatives

Alternative for local/air-gapped: **`nomic-embed-text`** via Ollama (768 dimensions, free, runs on CPU). Configured via:
```bash
EMBEDDING_PROVIDER=ollama          # or "openai"
EMBEDDING_MODEL=nomic-embed-text   # or "text-embedding-3-small"
EMBEDDING_DIMENSIONS=768           # or 1536
```

### Embedding Prefixes (Query vs Document)

To improve retrieval quality, use task-specific prefixes when embedding (per Brain Trust review — Hugging Face EmbeddingGemma research):

- **Search queries:** prefix with `"search_query: "` (nomic) or set `input_type="query"` (OpenAI)
- **Patent document chunks:** prefix with `"search_document: "` (nomic) or set `input_type="document"` (OpenAI)

This distinction helps the embedding model understand intent and significantly improves retrieval accuracy — queries are short and intent-focused, documents are long and descriptive.

### Chunking Strategy

Patent text is chunked before embedding:

- **Abstract:** Single chunk (typically < 300 words)
- **Claims:** One chunk per claim (preserves claim boundaries)
- **Description:** 512-token chunks with 64-token overlap, split at paragraph boundaries
- **Title:** Single chunk, stored as metadata rather than embedded separately

### Reranking (v2 Enhancement)

After initial vector retrieval from Qdrant (top-N candidates), a cross-encoder reranker can score results more precisely. Per Brain Trust review (Rost Glukhov — Reranking with Embedding Models), this second-pass reranking significantly improves relevance for patent search where subtle technical distinctions matter. Deferred to v2 — initial retrieval quality should be validated first.

---

## Appendix C: Encryption Key Management

### Default: AES-256-GCM in Postgres

```
ENCRYPTION_MASTER_KEY=<64-char hex string>   # In .env, generated on first setup
```

- Master key stored in `.env` file (not in database)
- Each API key encrypted with AES-256-GCM using the master key
- Unique IV (initialization vector) per encrypted value, stored alongside in `api_keys.iv`
- Key hint (last 4 chars) stored in plaintext for UI display
- On read: decrypt in application memory, never logged, never returned to frontend after initial save
- On master key rotation: re-encrypt all keys in a migration script

**Limitations acknowledged:** If `.env` is compromised, all keys are compromised. This is acceptable for self-hosted single-user/small-team deployments. For higher security, use the Vault backend.

### Advanced: OpenBao/Vault

```bash
SECRETS_BACKEND=vault
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=<token>
```

- Keys stored in Vault's KV-v2 engine at `secret/patent-platform/users/{user_id}/`
- Auto-rotation via Vault policies
- Full audit trail of every read/write
- Dynamic secrets with TTL for database credentials

---

## Appendix D: Authentication Flow

### Model: Multi-user, self-hosted

The platform is multi-user (supports teams, not just single-user). Auth is handled entirely by Supabase GoTrue.

### Supported Auth Methods (v1)

- **Email + password** — primary method, email verification required
- **Magic link** — passwordless email login
- **OAuth** — Google and GitHub providers (configured via Supabase Studio)

Additional OAuth providers can be added via Studio without code changes.

### JWT Structure

Supabase GoTrue issues JWTs with these claims:
```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "role": "authenticated",
  "aud": "authenticated",
  "exp": 1234567890
}
```

### Authorization Model (v1)

Simple — no roles beyond "authenticated user." All authenticated users have full access to their own data via Postgres row-level security policies (`auth.uid() = user_id`). No admin role in v1.

### FastAPI Middleware

`auth.py` extracts the JWT from the `Authorization: Bearer <token>` header, verifies it against Supabase's JWT secret, and injects `user_id` into the request state. Unauthenticated requests to protected endpoints return 401.

---

## Appendix E: API Request/Response Schemas

### POST /search

```json
// Request
{
  "project_id": "uuid",              // Optional — attach results to project
  "query": "wireless power transfer for implantable medical devices",
  "strategies": ["keyword", "classification", "citation"],  // Default: all
  "providers": ["patentsview", "uspto_odp"],                 // Default: all enabled
  "date_range": {"start": "2015-01-01", "end": "2025-12-31"}, // Optional
  "cpc_codes": ["A61N"],             // Optional — filter by classification
  "max_results": 50                  // Default: 50
}

// Response
{
  "total_hits": 234,
  "results": [
    {
      "patent_id": "US11234567",
      "title": "WIRELESS POWER TRANSFER SYSTEM FOR...",
      "abstract": "A system for wirelessly...",
      "date": "2023-05-15",
      "inventors": [{"first": "John", "last": "Smith"}],
      "assignees": [{"organization": "MedTech Inc"}],
      "cpc_codes": ["A61N1/372"],
      "provider": "patentsview",
      "strategy": "keyword"
    }
  ],
  "search_metadata": {
    "providers_queried": ["patentsview", "uspto_odp"],
    "duration_ms": 1250,
    "strategies_used": ["keyword", "classification"]
  }
}
```

### POST /analyze

```json
// Request
{
  "project_id": "uuid",
  "invention_description": "A system that...",
  "search_result_ids": ["uuid", "uuid"],     // Which prior art to compare against
  "checks": ["novelty", "obviousness", "eligibility"]  // Default: all
}

// Response
{
  "novelty": {
    "status": "caution",      // clear, caution, conflict
    "findings": [
      {
        "prior_art_id": "US11234567",
        "overlap": "Both describe wireless power transfer to implanted devices",
        "distinguishing_features": ["Our system uses adaptive frequency hopping"],
        "severity": "medium"
      }
    ]
  },
  "obviousness": { ... },
  "eligibility": { ... },
  "overall_recommendation": "Proceed with narrowed claims focusing on adaptive frequency hopping"
}
```

### POST /draft

```json
// Request
{
  "project_id": "uuid",
  "filing_format": "provisional",    // provisional, nonprovisional, pct
  "invention_description": "...",
  "prior_art_analysis_id": "uuid",   // Optional but recommended
  "preferences": {
    "claim_breadth": "balanced",     // broad, balanced, narrow
    "num_embodiments": 3,
    "technical_field": "medical devices"
  }
}

// Response
{
  "draft_id": "uuid",
  "version": 1,
  "title": "ADAPTIVE WIRELESS POWER TRANSFER SYSTEM FOR IMPLANTABLE MEDICAL DEVICES",
  "abstract": "A system for wirelessly... (148 words)",
  "specification": {
    "background": "...",
    "summary": "...",
    "detailed_description": "...",
    "embodiments": ["...", "...", "..."]
  },
  "claims": [
    {"number": 1, "type": "independent", "text": "A system comprising..."},
    {"number": 2, "type": "dependent", "depends_on": 1, "text": "The system of claim 1, wherein..."}
  ],
  "filing_checklist": ["Cover sheet (PTO/SB/16)", "Filing fee", "Specification", "Drawings"]
}
```

### POST /pipeline

```json
// Request
{
  "project_id": "uuid",       // Optional — creates new project if omitted
  "invention_description": "...",
  "filing_format": "provisional",
  "resume_from": "analyze"     // Optional — for re-entry
}

// Response (initial — then progress via Supabase Realtime)
{
  "pipeline_run_id": "uuid",
  "project_id": "uuid",
  "status": "running",
  "subscribe_channel": "pipeline_runs:eq.pipeline_run_id"
}
```

---

## Appendix F: Pipeline State Machine

```
        ┌──────────┐
        │ describe │ (user input received)
        └────┬─────┘
             │
        ┌────▼─────┐
        │  search  │ (parallel provider queries)
        └────┬─────┘
             │
        ┌────▼──────┐
        │  analyze  │ (prior art comparison)
        └────┬──────┘
             │
        ┌────▼──────────┐
        │  prior_art_   │ (warns if conflicts found)
        │  gate         │──── user overrides ────┐
        └────┬──────────┘                        │
             │ (clear / accepted)                │
        ┌────▼─────┐                        ┌────▼─────┐
        │  draft   │◄───────────────────────┤  draft   │
        └────┬─────┘                        └──────────┘
             │
        ┌────▼──────┐
        │  review   │ (101, 102, 103, 112, formalities)
        └────┬──────┘
             │
        ┌────▼──────┐
        │  export   │ (DOCX/PDF generation)
        └────┬──────┘
             │
        ┌────▼──────┐
        │ complete  │
        └───────────┘

Any stage can transition to:
  → failed (with error_message, retryable)
  → the stage itself (retry)
  → any previous stage (revision loop)
```

State persisted in `pipeline_runs` table. The `stages_completed` JSONB array tracks which stages have finished, enabling re-entry. On resume, the orchestrator reads `stages_completed` and starts from the first incomplete stage.

### Workflow Engine Upgrade Path (v2)

Per Brain Trust review (Rost Glukhov — Temporal Workflows): if pipeline complexity grows beyond the current 6-stage linear flow (e.g., parallel branching, conditional sub-workflows, long-running human-in-the-loop approval steps), migrate from the Postgres-backed state machine to **Temporal** workflow engine. Temporal provides durable execution, automatic retries, and built-in support for long-running workflows. For v1's linear pipeline, the current approach is appropriate and avoids unnecessary infrastructure.

---

## Appendix G: Additional Implementation Details

### Rate Limiting

Stored in Postgres (survives restarts), enforced in FastAPI middleware:

| Endpoint | Limit | Window | Reason |
|----------|-------|--------|--------|
| POST /search | 30 requests | per minute | Protects PatentsView's 45 req/min limit |
| POST /analyze | 10 requests | per minute | LLM-intensive |
| POST /draft | 5 requests | per minute | LLM-intensive, long-running |
| POST /pipeline | 3 requests | per minute | Full pipeline, heaviest workload |
| GET /health | Unlimited | — | Health checks |
| PUT /config | 10 requests | per minute | Config changes |

Limits are per-user (keyed by `user_id` from JWT). Configurable via environment variables (`RATE_LIMIT_SEARCH=30`, etc.).

### DOCX/PDF Export

Library: **`python-docx`** for DOCX, **`weasyprint`** for PDF generation.

Templates include USPTO formatting requirements:
- 8.5" x 11" paper (letter size) or A4 for PCT
- 1" top margin, 0.75" side margins
- Double-spaced specification text
- Line numbering in left margin (non-provisional)
- Times New Roman or Courier New, 12pt
- Claims on separate page, single sentence per claim
- Abstract on separate page, max 150 words

Generated files stored in Supabase Storage, downloadable via signed URLs.

**USPTO DOCX Rendering Warning** (per Brain Trust review — IPWatchdog):
The USPTO's transition to DOCX filing has documented rendering issues with mathematical formulas, embedded fonts, and complex formatting. Generated DOCX files should be:
- Tested against USPTO Patent Center's DOCX upload validator before actual filing
- Exported as **both DOCX and PDF** so users have a visual reference to compare against the DOCX rendering
- Accompanied by a disclaimer: *"Review all generated documents carefully before filing. AI-generated formatting may not meet all USPTO requirements. Have a patent attorney review before submission."*

### visual-explainer Interface Contract

The patent-diagrams skill communicates with visual-explainer via Claude Code's skill invocation:

1. `patent-diagrams` skill determines what to draw and generates structured content:
   ```markdown
   ## Diagram Request
   Type: flowchart
   Mode: formal (non-provisional)
   Title: FIG. 1 - System Architecture
   Reference numerals: {100: "wireless power system", 110: "transmitter", 120: "receiver"}
   Content: [Mermaid syntax with reference numbers as labels]
   ```

2. `patent-diagrams` invokes visual-explainer's `/generate-web-diagram` command with the content
3. visual-explainer renders the HTML page with Mermaid.js
4. If visual-explainer is not installed, the skill falls back to writing raw Mermaid syntax to a `.md` file and instructs the user to render it manually

### Error Handling Strategy

| Failure | Behavior |
|---------|----------|
| PatentsView API down | Continue with other enabled providers; warn user if no providers available |
| USPTO ODP down | Same — degrade gracefully, aggregate from remaining providers |
| All search providers down | Return error with message; suggest user configure additional providers or retry later |
| LLM returns malformed output | Retry once with stricter prompt; if still malformed, return partial result with warning |
| Qdrant unreachable | Fall back to pgvector if available; if neither, disable semantic search with warning |
| User's API key invalid | Return 403 with specific message ("SerpAPI key is invalid"); disable that provider for the request |
| Pipeline stage fails | Mark stage as `failed` with error_message; allow re-entry from that stage |
| Rate limit exceeded | Return 429 with `Retry-After` header |

### Standalone Mode (no Docker) Feature Degradation

| Feature | Full (Docker) | Standalone (SQLite) |
|---------|--------------|-------------------|
| Patent search (keyword) | All providers, parallel | PatentsView + USPTO via curl |
| Semantic search (vector) | Qdrant | Not available |
| Draft generation | Full, saved to DB | Full, saved to local files |
| Auth | Supabase (multi-user) | None (single-user) |
| Pipeline progress | Supabase Realtime | Terminal output |
| File storage | Supabase Storage | Local filesystem |
| Search history | Postgres | SQLite |
| Export (DOCX/PDF) | Full | Full (python-docx + weasyprint still work locally) |
| Examiner stats | PatentsView API | PatentsView API (same) |

### Logging

Framework: **`structlog`** (JSON structured logging).
- Each pipeline stage logs: `stage`, `user_id`, `project_id`, `duration_ms`, `tokens_used`, `api_calls`, `status`
- Log destination: stdout (Docker captures via `docker logs`)
- Log level configurable via `LOG_LEVEL=INFO` env var

### Testing Strategy

Framework: **`pytest`** with `pytest-asyncio` for async FastAPI tests.

| Layer | What's Tested | Target Coverage |
|-------|--------------|----------------|
| `core/models/` | Pydantic model validation, serialization | 95% |
| `core/search/` | Provider response parsing, aggregation, deduplication | 85% |
| `core/analysis/` | Claims parsing, rejection detection logic | 80% |
| `core/drafting/` | Template generation, format compliance | 80% |
| `core/pipeline.py` | Stage transitions, re-entry, error handling | 90% |
| `api/routes/` | Endpoint integration tests (with test DB) | 80% |
| `skills/*/test_cases.md` | Manual LLM evaluation harness — not automated pytest | N/A |

Skill test cases are manual evaluation scripts: run a test invention through the skill, compare output against expected structure and content. These validate LLM output quality, not deterministic code paths.

### PatentsView API Key Note

As of 2026, PatentsView requires an API key passed via the `X-Api-Key` header. Registration is free at patentsview.org. The `.env.example` includes `PATENTSVIEW_API_KEY=` with a comment directing users to the registration page.

---

## Out of Scope (v1)

- Chinese patent support (patent-architect project — may be added later)
- Design patent applications (utility only in v1)
- Automated USPTO filing (generates documents for manual filing or attorney submission)
- Real-time USPTO examiner interaction
- Patent portfolio management (single application focus in v1)
- Billing / SaaS subscription system
- Multi-language support (English only; PCT multi-language abstracts not supported)
- Database migration tooling (v2 concern — will use Alembic when needed)
- ExaminerStats data source (v1 uses PatentsView examiner data if available; dedicated examiner analytics deferred)
- Claim chart generation in analysis module (v1 generates comparison tables; structured claim-to-prior-art mapping is a v2 feature; ClaimChart.tsx component is scaffolded but populated manually)
