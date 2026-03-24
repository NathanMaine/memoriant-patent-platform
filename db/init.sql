-- Memoriant Patent Platform — Database Schema

CREATE EXTENSION IF NOT EXISTS "pgvector";

CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.user_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    llm_provider TEXT NOT NULL DEFAULT 'claude',
    llm_endpoint TEXT,
    llm_model TEXT DEFAULT 'claude-opus-4-6',
    extended_thinking BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

CREATE TABLE IF NOT EXISTS public.api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    encrypted_key BYTEA NOT NULL,
    iv BYTEA NOT NULL,
    key_hint TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

CREATE TABLE IF NOT EXISTS public.patent_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    technical_field TEXT,
    filing_format TEXT,
    status TEXT DEFAULT 'draft',
    provisional_filed_at TIMESTAMPTZ,
    nonprovisional_deadline TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.search_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.patent_projects(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    patent_id TEXT NOT NULL,
    patent_title TEXT NOT NULL,
    patent_abstract TEXT,
    patent_date DATE,
    inventors JSONB,
    assignees JSONB,
    cpc_codes JSONB,
    relevance_score FLOAT,
    relevance_notes TEXT,
    search_strategy TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.draft_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.patent_projects(id) ON DELETE CASCADE,
    version INT NOT NULL DEFAULT 1,
    filing_format TEXT NOT NULL,
    title TEXT NOT NULL,
    abstract TEXT,
    specification JSONB NOT NULL,
    claims JSONB NOT NULL,
    drawings_description TEXT,
    ads_data JSONB,
    review_notes JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.patent_projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    current_stage TEXT NOT NULL,
    stage_status TEXT NOT NULL,
    stage_progress JSONB,
    stages_completed JSONB DEFAULT '[]',
    error_message TEXT,
    metrics JSONB,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.file_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES public.patent_projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    action TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row-level security
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patent_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.draft_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.file_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users own data" ON public.profiles FOR ALL USING (auth.uid() = id);
CREATE POLICY "Users own data" ON public.patent_projects FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users own search results" ON public.search_results FOR ALL USING (project_id IN (SELECT id FROM public.patent_projects WHERE user_id = auth.uid()));
CREATE POLICY "Users own drafts" ON public.draft_applications FOR ALL USING (project_id IN (SELECT id FROM public.patent_projects WHERE user_id = auth.uid()));
CREATE POLICY "Users own pipeline runs" ON public.pipeline_runs FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users own file history" ON public.file_history FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users own configs" ON public.user_configs FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users own api keys" ON public.api_keys FOR ALL USING (auth.uid() = user_id);

-- Performance indexes
CREATE INDEX idx_patent_projects_user ON patent_projects(user_id, updated_at DESC);
CREATE INDEX idx_search_results_project ON search_results(project_id, created_at DESC);
CREATE INDEX idx_draft_applications_project ON draft_applications(project_id, version DESC);
CREATE INDEX idx_pipeline_runs_project ON pipeline_runs(project_id, started_at DESC);
CREATE INDEX idx_pipeline_runs_user ON pipeline_runs(user_id, started_at DESC);
CREATE INDEX idx_file_history_project ON file_history(project_id, created_at DESC);
CREATE INDEX idx_patent_projects_status ON patent_projects(user_id, status);
CREATE INDEX idx_patent_projects_deadline ON patent_projects(nonprovisional_deadline) WHERE nonprovisional_deadline IS NOT NULL;
