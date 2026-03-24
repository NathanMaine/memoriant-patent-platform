<p align="center">
  <img src="https://img.shields.io/badge/status-in%20development-yellow" alt="Status: In Development" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT" />
  <img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/react-18-61DAFB" alt="React 18" />
  <img src="https://img.shields.io/badge/docker-compose-2496ED" alt="Docker Compose" />
</p>

# Memoriant Patent Platform

A full-pipeline patent platform that takes inventors from **idea to filing-ready draft**. Search prior art across multiple databases, analyze patentability, generate complete patent applications, and export documents ready for attorney review or filing.

Built for [Memoriant](https://github.com/NathanMaine) — self-hosted, model-agnostic, and distributable.

---

## What It Does

```
Describe Invention  ──>  Prior Art Search  ──>  Analysis  ──>  Draft Application  ──>  Review  ──>  Export
```

| Stage | What Happens |
|-------|-------------|
| **Describe** | Enter your invention idea, key features, and technical field |
| **Search** | Parallel prior art search across PatentsView, USPTO, and Google Patents |
| **Analyze** | Novelty (102), obviousness (103), eligibility (101), claims (112), formalities |
| **Draft** | Generate complete patent application — provisional, non-provisional, or PCT |
| **Review** | AI-assisted review against all major USPTO rejection types |
| **Export** | Download as DOCX + PDF, formatted to USPTO specifications |

---

## Key Features

**Patent Search**
- Multi-provider: PatentsView (free), USPTO Open Data Portal (free), Google Patents via SerpAPI (paid, opt-in)
- Multi-strategy: keyword, CPC classification, citation chain, inventor/assignee, date range
- Follows the USPTO 7-step prior art search methodology
- Parallel search with result deduplication and relevance scoring

**Patent Analysis**
- Subject matter eligibility (35 USC 101)
- Novelty pre-screening (35 USC 102)
- Obviousness assessment (35 USC 103)
- Claims definiteness (35 USC 112(b))
- Specification enablement (35 USC 112(a))
- Formalities compliance (MPEP 608)

**Patent Drafting**
- USPTO provisional application
- USPTO non-provisional (utility) application
- PCT international format
- Multiple embodiments with broad-to-narrow fallback claims
- Application Data Sheet (ADS) generation
- 12-month provisional deadline tracking

**Model-Agnostic AI**
- Claude API (default, optimized for Opus 4.6 with extended thinking)
- Ollama, vLLM, LM Studio — any OpenAI-compatible endpoint
- Free by default, paid search sources opt-in

---

## Architecture

```
                    ┌─────────────────────────────┐
                    │     Delivery Layer           │
                    │  ┌─────────┐  ┌───────────┐ │
                    │  │ FastAPI │  │ Claude    │ │
                    │  │   API   │  │ Code      │ │
                    │  │         │  │ Skills    │ │
                    │  └────┬────┘  └─────┬─────┘ │
                    └───────┼─────────────┼───────┘
                            │             │
                    ┌───────▼─────────────▼───────┐
                    │     Core Library             │
                    │  ┌──────────────────────┐   │
                    │  │  Pipeline            │   │
                    │  │  Orchestrator        │   │
                    │  └──────────┬───────────┘   │
                    │  ┌──────┐ ┌┴─────┐ ┌─────┐ │
                    │  │Search│ │Analy-│ │Draft│ │
                    │  │      │ │sis   │ │     │ │
                    │  └──┬───┘ └──┬───┘ └──┬──┘ │
                    │     │        │        │     │
                    │  ┌──▼────────▼────────▼──┐  │
                    │  │   Domain Models        │  │
                    │  └───────────────────────┘  │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │     Infrastructure           │
                    │  ┌─────┐ ┌───────┐ ┌──────┐ │
                    │  │ LLM │ │Storage│ │Search│ │
                    │  │     │ │       │ │ APIs │ │
                    │  └─────┘ └───────┘ └──────┘ │
                    └─────────────────────────────┘
```

**Modular core, multiple frontends.** The core library handles all patent logic. The FastAPI web service and Claude Code skills are just different ways to access it.

---

## Quick Start

### Full Platform (Docker)

```bash
git clone https://github.com/NathanMaine/memoriant-patent-platform.git
cd memoriant-patent-platform
cp .env.example .env
# Edit .env with your API keys
docker compose up
```

Open `http://localhost:3000` for the web UI, `http://localhost:8080` for Supabase Studio.

### Claude Code Skills Only (No Docker)

```bash
# Install the skills into Claude Code
cp -r skills/ ~/.claude/skills/patent/
# Configure your provider
claude /patent-config
# Run a search
claude /patent-search "wireless power transfer for medical implants"
```

### Core Library Only (Python)

```bash
pip install memoriant-patent-core
```

```python
from memoriant_patent_core import Pipeline, Config

config = Config(llm_provider="claude", anthropic_api_key="sk-...")
pipeline = Pipeline(config)
result = pipeline.run("A system for adaptive wireless power transfer...")
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Core Library** | Python 3.11+, Pydantic v2 |
| **LLM Providers** | Anthropic SDK (Claude), OpenAI-compat (Ollama/vLLM/LM Studio) |
| **Web API** | FastAPI, structlog, python-docx, weasyprint |
| **Frontend** | React 18, Vite, TypeScript, Supabase JS |
| **Database** | PostgreSQL 15 + pgvector (via Supabase) |
| **Vector Search** | Qdrant (primary), pgvector (fallback) |
| **Auth** | Supabase GoTrue (email, OAuth, magic links) |
| **Infrastructure** | Docker Compose, self-hosted Supabase |
| **Diagrams** | visual-explainer + Mermaid.js |
| **Testing** | pytest, pytest-asyncio |

---

## Configuration

```bash
# .env.example

# LLM Provider (Claude is default)
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-opus-4-6
CLAUDE_EXTENDED_THINKING=true

# Alternative LLM Providers (optional)
# OLLAMA_BASE_URL=http://localhost:11434
# VLLM_BASE_URL=http://localhost:8000

# Search Providers — Free (default on)
PATENTSVIEW_API_KEY=

# Search Providers — Paid (opt-in)
# SERPAPI_KEY=
```

Free search sources are on by default. Paid sources require explicit API key configuration. No surprise costs.

---

## Deployment Options

| Environment | What You Run | What You Get |
|-------------|-------------|-------------|
| **Self-hosted server** | `docker compose up` | Full platform — web UI, API, auth, vector search |
| **Developer laptop** | `pip install memoriant-patent-core` | Core library with SQLite, no Docker needed |
| **Claude Code** | Install skills directory | Patent tools as slash commands |

The Docker stack includes Supabase (auth + database + storage + realtime), Qdrant (vector search), FastAPI (backend), and React (frontend). All containers run hardened: non-root, read-only filesystem, dropped capabilities, network segmentation.

---

## Project Roadmap

- [x] Design specification (Brain Trust reviewed)
- [ ] **Phase 1:** Core Foundation — models, LLM abstraction, storage, Docker infrastructure
- [ ] **Phase 2:** Search & Analysis — PatentsView, USPTO, analysis modules (101-112)
- [ ] **Phase 3:** Drafting & Pipeline — application generation, pipeline orchestrator, API
- [ ] **Phase 4:** Frontend & Skills — React web app, Claude Code skills & agents

---

## Important Disclaimer

This platform is a **research and drafting aid**, not a substitute for professional legal counsel. Patent law is complex, and the quality of your patent protection depends on experienced legal guidance.

- Always have a qualified patent attorney review applications before filing
- AI-generated analysis may not catch all issues an experienced examiner would raise
- Generated DOCX documents should be validated against USPTO Patent Center before filing
- This tool does not provide legal advice

---

## License

[MIT](LICENSE)

---

Built by [Nathan Maine](https://github.com/NathanMaine)
