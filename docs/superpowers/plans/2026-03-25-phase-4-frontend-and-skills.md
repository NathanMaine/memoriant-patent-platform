# Phase 4: Frontend & Skills — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the React web frontend with patent wizard workflow, and Claude Code skills/agents for power users — completing the full platform with both UI and CLI access.

**Architecture:** React 18 + Vite + TypeScript frontend consuming the FastAPI backend. Supabase JS client for auth and realtime. Claude Code skills as standalone markdown files that call the core library or API.

**Tech Stack:** React 18, Vite, TypeScript, Supabase JS, TailwindCSS. Claude Code skill format (YAML frontmatter markdown).

**Requirements:** 100% test coverage on Python (skills test harness). Frontend: component tests where practical. Structured logging.

---

## File Structure

```
web/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── tailwind.config.js
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── services/
│   │   ├── api.ts                # FastAPI client (typed)
│   │   └── supabase.ts           # Supabase client (auth, realtime)
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── usePipeline.ts        # Realtime pipeline progress
│   │   └── usePatentSearch.ts
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── Dashboard.tsx
│   │   ├── NewPatent.tsx          # Wizard workflow
│   │   ├── SearchResults.tsx
│   │   ├── DraftEditor.tsx
│   │   └── Settings.tsx
│   └── components/
│       ├── PipelineProgress.tsx
│       ├── PatentCard.tsx
│       ├── ClaimsTree.tsx
│       ├── ComparisonTable.tsx
│       └── FileHistory.tsx
skills/
├── patent-search/
│   └── skill.md
├── patent-draft/
│   └── skill.md
├── patent-review/
│   └── skill.md
├── patent-diagrams/
│   └── skill.md
├── patent-pipeline/
│   └── skill.md
└── patent-config/
    └── skill.md
agents/
├── prior-art-searcher.md
├── patent-drafter.md
├── patent-reviewer.md
└── patent-illustrator.md
```

---

### Task 1: React Project Scaffolding

**Files:**
- Create: `web/` directory with Vite + React + TypeScript + TailwindCSS setup

- [ ] **Step 1:** Initialize React project with Vite
```bash
cd /tmp/memoriant-patent-platform && npm create vite@latest web -- --template react-ts
cd web && npm install && npm install -D tailwindcss @tailwindcss/vite
npm install @supabase/supabase-js
```
- [ ] **Step 2:** Configure Tailwind, add base layout in App.tsx
- [ ] **Step 3:** Create services/api.ts with typed fetch wrapper pointing at localhost:8080
- [ ] **Step 4:** Create services/supabase.ts with Supabase client init from env vars
- [ ] **Step 5:** Verify dev server starts: `npm run dev`
- [ ] **Step 6:** Commit: `git commit -m "feat: React frontend scaffolding with Vite + TypeScript + Tailwind"`

---

### Task 2: Auth (Login Page + useAuth Hook)

- [ ] Create `src/hooks/useAuth.ts` — wraps Supabase auth (signUp, signIn, signOut, session)
- [ ] Create `src/pages/Login.tsx` — email/password form, magic link option
- [ ] Route guard in App.tsx — redirect to Login if not authenticated
- [ ] Commit: `git commit -m "feat: auth flow with Supabase (login, signup, magic link)"`

---

### Task 3: Dashboard Page

- [ ] Create `src/pages/Dashboard.tsx` — lists recent patent projects, drafts in progress, filing deadlines
- [ ] Create `src/components/PatentCard.tsx` — displays patent project summary
- [ ] Fetch projects from API on load
- [ ] Commit: `git commit -m "feat: dashboard page with patent project listing"`

---

### Task 4: NewPatent Wizard

- [ ] Create `src/pages/NewPatent.tsx` — multi-step wizard with steps: Describe, Search, Analyze, Draft, Review, Export
- [ ] Create `src/components/PipelineProgress.tsx` — shows current stage with progress bar
- [ ] Create `src/hooks/usePipeline.ts` — Supabase Realtime subscription for pipeline_runs updates
- [ ] Step 1 (Describe): text area for invention description, technical field selector, filing format picker
- [ ] Step 2 (Search): triggers search, shows live results via PipelineProgress
- [ ] Step 3 (Analyze): shows analysis results with severity indicators
- [ ] Step 4 (Draft): shows generated application preview
- [ ] Step 5 (Review): shows review findings, allows edits
- [ ] Step 6 (Export): download DOCX + PDF buttons
- [ ] Commit: `git commit -m "feat: NewPatent wizard with full pipeline workflow"`

---

### Task 5: Search Results + Draft Editor Pages

- [ ] Create `src/pages/SearchResults.tsx` — prior art results with comparison table
- [ ] Create `src/components/ComparisonTable.tsx` — invention vs prior art features
- [ ] Create `src/components/ClaimsTree.tsx` — hierarchical view of independent + dependent claims
- [ ] Create `src/pages/DraftEditor.tsx` — view/edit generated application sections
- [ ] Create `src/components/FileHistory.tsx` — audit trail of actions
- [ ] Commit: `git commit -m "feat: search results, draft editor, and supporting components"`

---

### Task 6: Settings Page

- [ ] Create `src/pages/Settings.tsx` — configure LLM provider, search providers, API keys
- [ ] API key input fields with "last 4 chars" display after save
- [ ] LLM provider selector (Claude / Ollama / vLLM / LM Studio) with endpoint URL
- [ ] Search provider toggles (PatentsView on, USPTO on, SerpAPI off by default)
- [ ] Commit: `git commit -m "feat: settings page for provider and API key configuration"`

---

### Task 7: Claude Code Skills (6 skills)

- [ ] Create `skills/patent-search/skill.md` — USPTO 7-step search methodology, PatentsView API reference, search strategies, result formatting
- [ ] Create `skills/patent-draft/skill.md` — filing format selection, drafting workflow, USPTO requirements per format
- [ ] Create `skills/patent-review/skill.md` — all rejection types (101-112 + formalities), review workflow, MPEP citations
- [ ] Create `skills/patent-diagrams/skill.md` — visual-explainer integration, reference numbering, formal/informal modes
- [ ] Create `skills/patent-pipeline/skill.md` — end-to-end orchestration, prior art gate, progress tracking
- [ ] Create `skills/patent-config/skill.md` — provider configuration, API key management, mode selection
- [ ] Commit: `git commit -m "feat: 6 Claude Code skills for patent workflow"`

---

### Task 8: Claude Code Agents (4 agents)

- [ ] Create `agents/prior-art-searcher.md` — autonomous 7-step search, multi-strategy, hybrid AI+manual
- [ ] Create `agents/patent-drafter.md` — multi-embodiment, layered claims, filing format awareness
- [ ] Create `agents/patent-reviewer.md` — full rejection screening, MPEP citations, suggested fixes
- [ ] Create `agents/patent-illustrator.md` — diagram generation via visual-explainer, reference numerals
- [ ] Commit: `git commit -m "feat: 4 Claude Code agents for patent workflow"`

---

### Task 9: Final Verification + Push

- [ ] Python tests: `pytest tests/ --cov=core --cov=api --cov-report=term-missing` → 100%
- [ ] Frontend builds: `cd web && npm run build` → success
- [ ] All skills have valid YAML frontmatter
- [ ] `git push origin main`

---

## Phase 4 Completion Checklist

- [ ] React frontend builds and serves
- [ ] Auth flow works (login, signup, magic link)
- [ ] Dashboard shows patent projects
- [ ] NewPatent wizard completes full pipeline
- [ ] Search results display with comparison table
- [ ] Draft editor allows viewing/editing
- [ ] Settings page configures all providers
- [ ] 6 Claude Code skills with valid frontmatter
- [ ] 4 Claude Code agents with clear workflows
- [ ] Python backend: 100% test coverage maintained
- [ ] All code pushed
