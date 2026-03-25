# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.1.0] - 2026-03-25

### Added

- Core library: Pydantic domain models (Patent, Claim, SearchResult, DraftApplication)
- LLM abstraction: Claude SDK + OpenAI-compatible providers (Ollama, vLLM, LM Studio)
- Storage: SQLite, Supabase Postgres, Qdrant, pgvector fallback
- AES-256-GCM encrypted API key storage
- Search providers: PatentsView, USPTO Open Data Portal, SerpAPI (paid opt-in)
- Search aggregator with parallel execution and deduplication
- Analysis modules: prior art, novelty (102), obviousness (103), claims (112b), specification (112a), eligibility (101), formalities (MPEP 608)
- Embedding pipeline with chunking (abstract, claims, description)
- Patent drafters: provisional, non-provisional (utility), PCT international
- Pipeline orchestrator with stage re-entry and prior art gate
- DOCX + PDF export with USPTO formatting
- FastAPI backend with JWT auth, rate limiting, structured logging
- React frontend: Login, Dashboard, NewPatent wizard, SearchResults, DraftEditor, Settings
- 6 Claude Code skills: patent-search, patent-draft, patent-review, patent-diagrams, patent-pipeline, patent-config
- 4 Claude Code agents: prior-art-searcher, patent-drafter, patent-reviewer, patent-illustrator
- Docker Compose deployment (Supabase self-hosted + Qdrant)
- 595 tests with 100% coverage (2,462 statements)
