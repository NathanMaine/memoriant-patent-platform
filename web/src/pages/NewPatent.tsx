import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { usePipeline } from '../hooks/usePipeline';
import { usePatentSearch } from '../hooks/usePatentSearch';
import { PipelineProgress, type PipelineStep } from '../components/PipelineProgress';
import { PatentCard } from '../components/PatentCard';

const TECHNICAL_FIELDS = [
  'Electrical / Electronics',
  'Mechanical',
  'Software / Computing',
  'Biotechnology / Life Sciences',
  'Chemistry / Materials',
  'Medical Devices',
  'Telecommunications',
  'Semiconductor',
  'Other',
];

const FILING_FORMATS = [
  { value: 'provisional', label: 'Provisional Application (12-month placeholder)' },
  { value: 'nonprovisional', label: 'Nonprovisional Application (full examination)' },
  { value: 'pct', label: 'PCT International Application' },
];

type SeverityLevel = 'clear' | 'caution' | 'conflict';

const SEVERITY_STYLES: Record<SeverityLevel, string> = {
  clear: 'bg-green-100 text-green-800 border-green-200',
  caution: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  conflict: 'bg-red-100 text-red-800 border-red-200',
};

interface AnalysisResult {
  overall_severity: SeverityLevel;
  summary: string;
  findings: Array<{
    aspect: string;
    severity: SeverityLevel;
    detail: string;
  }>;
}

interface DraftResult {
  title: string;
  abstract: string;
  specification_preview: string;
  claims_count: number;
  project_id?: string;
}

function buildSteps(currentStep: number, pipelineStatus: string): PipelineStep[] {
  const labels = ['Describe', 'Search', 'Analyze', 'Draft', 'Review', 'Export'];
  return labels.map((label, i) => {
    let status: PipelineStep['status'] = 'pending';
    if (i < currentStep) status = 'completed';
    else if (i === currentStep) {
      if (pipelineStatus === 'failed') status = 'failed';
      else if (pipelineStatus === 'running') status = 'running';
      else status = 'pending';
    }
    return { key: label.toLowerCase(), label, status };
  });
}

export function NewPatent() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [projectId, setProjectId] = useState<string | undefined>();

  // Step 1 form state
  const [description, setDescription] = useState('');
  const [technicalField, setTechnicalField] = useState('');
  const [filingFormat, setFilingFormat] = useState('provisional');

  // Step 2 search
  const { loading: searchLoading, results: searchResults, error: searchError, search } = usePatentSearch();

  // Pipeline realtime
  const { stage, progress, status: pipelineStatus } = usePipeline(projectId);

  // Step 3 analysis
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Step 4 draft
  const [draft, setDraft] = useState<DraftResult | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);

  // Step 5 review
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewSaved, setReviewSaved] = useState(false);

  // Full pipeline
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  const steps = buildSteps(step, pipelineStatus);

  async function handleSearch() {
    if (!description.trim()) return;
    await search({ description, technical_field: technicalField });
    setStep(1);
  }

  async function handleAnalyze() {
    setAnalysisError(null);
    setStep(2);
    try {
      const result = await api.analyze({
        description,
        technical_field: technicalField,
        prior_art: searchResults.map((r) => r.patent_number),
      }) as AnalysisResult;
      setAnalysis(result);
    } catch (err) {
      setAnalysisError(err instanceof Error ? err.message : 'Analysis failed');
    }
  }

  async function handleDraft() {
    setDraftError(null);
    setStep(3);
    try {
      const result = await api.draft({
        description,
        technical_field: technicalField,
        filing_format: filingFormat,
        analysis,
      }) as DraftResult;
      setDraft(result);
      if (result.project_id) setProjectId(result.project_id);
    } catch (err) {
      setDraftError(err instanceof Error ? err.message : 'Draft generation failed');
    }
  }

  async function handleRunFullPipeline() {
    if (!description.trim()) return;
    setPipelineRunning(true);
    setPipelineError(null);
    try {
      const result = await api.pipeline({
        description,
        technical_field: technicalField,
        filing_format: filingFormat,
      }) as { project_id?: string };
      if (result.project_id) {
        setProjectId(result.project_id);
        navigate(`/draft/${result.project_id}`);
      }
    } catch (err) {
      setPipelineError(err instanceof Error ? err.message : 'Pipeline failed');
    } finally {
      setPipelineRunning(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-14 gap-4">
            <button
              onClick={() => navigate('/')}
              className="text-sm text-gray-500 hover:text-gray-900"
            >
              &larr; Dashboard
            </button>
            <h1 className="text-base font-semibold text-gray-900">New Patent Application</h1>
          </div>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6">
          <PipelineProgress
            steps={steps}
            progress={pipelineStatus === 'running' ? progress : undefined}
            currentStage={stage || undefined}
          />
        </div>

        {/* Step 0: Describe */}
        {step === 0 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Describe Your Invention</h2>
            <p className="text-sm text-gray-500 mb-5">
              Provide a clear and detailed description. The more specific you are, the more accurate the prior art search and draft will be.
            </p>

            <div className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Invention Description <span className="text-red-500">*</span>
                </label>
                <textarea
                  rows={8}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe the invention in detail, including the problem it solves, the technical approach, and key novel aspects..."
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent resize-y"
                />
              </div>

              <div className="grid sm:grid-cols-2 gap-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Technical Field
                  </label>
                  <select
                    value={technicalField}
                    onChange={(e) => setTechnicalField(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 bg-white"
                  >
                    <option value="">Select a field...</option>
                    {TECHNICAL_FIELDS.map((f) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Filing Format
                  </label>
                  <div className="space-y-2">
                    {FILING_FORMATS.map((f) => (
                      <label key={f.value} className="flex items-start gap-2.5 cursor-pointer">
                        <input
                          type="radio"
                          name="filing_format"
                          value={f.value}
                          checked={filingFormat === f.value}
                          onChange={() => setFilingFormat(f.value)}
                          className="mt-0.5 accent-gray-900"
                        />
                        <span className="text-sm text-gray-700 leading-snug">{f.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleSearch}
                  disabled={!description.trim() || searchLoading}
                  className="px-5 py-2.5 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {searchLoading ? 'Searching...' : 'Search Prior Art'}
                </button>
                <button
                  onClick={handleRunFullPipeline}
                  disabled={!description.trim() || pipelineRunning}
                  className="px-5 py-2.5 bg-blue-700 text-white text-sm font-medium rounded-lg hover:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {pipelineRunning ? 'Running Pipeline...' : 'Run Full Pipeline'}
                </button>
              </div>

              {pipelineError && (
                <div className="rounded-lg bg-red-50 border border-red-200 p-3">
                  <p className="text-sm text-red-700">{pipelineError}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Step 1: Search Results */}
        {step >= 1 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Prior Art Search Results</h2>
              {step === 1 && (
                <button
                  onClick={handleAnalyze}
                  disabled={searchLoading}
                  className="px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 transition-colors"
                >
                  Analyze Results
                </button>
              )}
            </div>

            {searchLoading && (
              <div className="flex items-center gap-3 py-8 justify-center">
                <div className="animate-spin w-5 h-5 border-2 border-gray-300 border-t-gray-900 rounded-full" />
                <span className="text-sm text-gray-500">Searching patent databases...</span>
              </div>
            )}

            {searchError && (
              <div className="rounded-lg bg-red-50 border border-red-200 p-3">
                <p className="text-sm text-red-700">{searchError}</p>
              </div>
            )}

            {!searchLoading && searchResults.length === 0 && !searchError && (
              <p className="text-sm text-gray-400 text-center py-6">No prior art found for this description.</p>
            )}

            {!searchLoading && searchResults.length > 0 && (
              <div className="grid gap-3 sm:grid-cols-2">
                {searchResults.map((r) => (
                  <PatentCard
                    key={r.patent_number}
                    patent={{
                      patent_number: r.patent_number,
                      title: r.title,
                      abstract: r.abstract,
                      inventors: r.inventors,
                      filing_date: r.filing_date,
                      status: r.severity,
                      assignee: r.assignee,
                      relevance_score: r.relevance_score,
                    }}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 2: Analysis */}
        {step >= 2 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Patentability Analysis</h2>
              {step === 2 && analysis && (
                <button
                  onClick={handleDraft}
                  className="px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
                >
                  Generate Draft
                </button>
              )}
            </div>

            {!analysis && !analysisError && (
              <div className="flex items-center gap-3 py-8 justify-center">
                <div className="animate-spin w-5 h-5 border-2 border-gray-300 border-t-gray-900 rounded-full" />
                <span className="text-sm text-gray-500">Analyzing prior art...</span>
              </div>
            )}

            {analysisError && (
              <div className="rounded-lg bg-red-50 border border-red-200 p-3">
                <p className="text-sm text-red-700">{analysisError}</p>
              </div>
            )}

            {analysis && (
              <div className="space-y-4">
                <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-medium ${SEVERITY_STYLES[analysis.overall_severity]}`}>
                  Overall Assessment: {analysis.overall_severity.charAt(0).toUpperCase() + analysis.overall_severity.slice(1)}
                </div>
                <p className="text-sm text-gray-700 leading-relaxed">{analysis.summary}</p>
                {analysis.findings && analysis.findings.length > 0 && (
                  <div className="space-y-2">
                    {analysis.findings.map((f, i) => (
                      <div key={i} className={`p-3 rounded-lg border ${SEVERITY_STYLES[f.severity]}`}>
                        <p className="text-sm font-semibold">{f.aspect}</p>
                        <p className="text-sm mt-0.5 opacity-90">{f.detail}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 3: Draft */}
        {step >= 3 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Generated Draft</h2>
              {step === 3 && draft && (
                <button
                  onClick={() => setStep(4)}
                  className="px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
                >
                  Proceed to Review
                </button>
              )}
            </div>

            {!draft && !draftError && (
              <div className="flex items-center gap-3 py-8 justify-center">
                <div className="animate-spin w-5 h-5 border-2 border-gray-300 border-t-gray-900 rounded-full" />
                <span className="text-sm text-gray-500">Generating patent application...</span>
              </div>
            )}

            {draftError && (
              <div className="rounded-lg bg-red-50 border border-red-200 p-3">
                <p className="text-sm text-red-700">{draftError}</p>
              </div>
            )}

            {draft && (
              <div className="space-y-4">
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Title</p>
                  <p className="text-base font-medium text-gray-900">{draft.title}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Abstract</p>
                  <p className="text-sm text-gray-700 leading-relaxed">{draft.abstract}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Specification (Preview)</p>
                  <p className="text-sm text-gray-700 leading-relaxed line-clamp-6">{draft.specification_preview}</p>
                </div>
                <div className="pt-2 border-t border-gray-100">
                  <p className="text-sm text-gray-500">{draft.claims_count} claim(s) generated</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step 4: Review */}
        {step >= 4 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Review</h2>
              {step === 4 && (
                <button
                  onClick={() => { setReviewSaved(true); setStep(5); }}
                  className="px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
                >
                  Approve and Continue
                </button>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Review Notes / Amendments
              </label>
              <textarea
                rows={5}
                value={reviewNotes}
                onChange={(e) => { setReviewNotes(e.target.value); setReviewSaved(false); }}
                placeholder="Record any amendments, notes for the attorney, or items to address before filing..."
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 resize-y"
              />
              {reviewSaved && (
                <p className="text-xs text-green-600 mt-1">Review notes saved.</p>
              )}
            </div>
          </div>
        )}

        {/* Step 5: Export */}
        {step >= 5 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Export Application</h2>
            <p className="text-sm text-gray-600 mb-5">
              Your patent application is ready for export. Download in your preferred format.
            </p>
            <div className="flex gap-3 flex-wrap">
              <button
                className="px-5 py-2.5 bg-blue-700 text-white text-sm font-medium rounded-lg hover:bg-blue-800 transition-colors"
                onClick={() => {
                  if (draft?.project_id) navigate(`/draft/${draft.project_id}`);
                }}
              >
                Download DOCX
              </button>
              <button
                className="px-5 py-2.5 bg-gray-700 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
                onClick={() => {
                  if (draft?.project_id) navigate(`/draft/${draft.project_id}`);
                }}
              >
                Download PDF
              </button>
              {draft?.project_id && (
                <button
                  className="px-5 py-2.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors"
                  onClick={() => navigate(`/draft/${draft.project_id}`)}
                >
                  Open Full Editor
                </button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
