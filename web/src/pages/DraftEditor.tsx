import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { ClaimsTree, type Claim } from '../components/ClaimsTree';
import { FileHistory, type HistoryEntry } from '../components/FileHistory';

interface DraftSection {
  key: string;
  label: string;
  content: string;
}

interface FullDraft {
  title: string;
  abstract: string;
  specification: string;
  background: string;
  summary: string;
  claims: Claim[];
  history: HistoryEntry[];
  status?: string;
  filing_format?: string;
}

const SECTION_KEYS: Array<{ key: keyof Omit<FullDraft, 'claims' | 'history' | 'status' | 'filing_format'>; label: string }> = [
  { key: 'title', label: 'Title' },
  { key: 'abstract', label: 'Abstract' },
  { key: 'background', label: 'Background' },
  { key: 'summary', label: 'Summary of Invention' },
  { key: 'specification', label: 'Detailed Description' },
];

type ActiveTab = 'document' | 'claims' | 'history';

export function DraftEditor() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [draft, setDraft] = useState<FullDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('document');
  const [editingSection, setEditingSection] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  useEffect(() => {
    if (!projectId) return;
    async function load() {
      try {
        const data = await api.draft({ project_id: projectId, fetch_only: true }) as FullDraft;
        setDraft(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load draft');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [projectId]);

  function startEdit(key: string, currentValue: string) {
    setEditingSection(key);
    setEditValue(currentValue);
  }

  function cancelEdit() {
    setEditingSection(null);
    setEditValue('');
  }

  function saveEdit(key: string) {
    if (!draft) return;
    setDraft({ ...draft, [key]: editValue });
    setEditingSection(null);
    setEditValue('');
  }

  const sections: DraftSection[] = draft
    ? SECTION_KEYS.map(({ key, label }) => ({
        key,
        label,
        content: (draft[key] as string) ?? '',
      }))
    : [];

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14 gap-4">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/')}
                className="text-sm text-gray-500 hover:text-gray-900"
              >
                &larr; Dashboard
              </button>
              <h1 className="text-base font-semibold text-gray-900">
                {draft?.title ?? 'Draft Editor'}
              </h1>
              {draft?.status && (
                <span className="hidden sm:inline text-xs font-medium px-2 py-1 rounded-full bg-gray-100 text-gray-700">
                  {draft.status}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <button className="px-3 py-1.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors">
                Export DOCX
              </button>
              <button className="px-3 py-1.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors">
                Export PDF
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin w-6 h-6 border-2 border-gray-300 border-t-gray-900 rounded-full" />
            <span className="ml-3 text-sm text-gray-500">Loading draft...</span>
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-4">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {!loading && !error && !draft && (
          <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
            <p className="text-sm text-gray-500">No draft found for this project.</p>
          </div>
        )}

        {draft && (
          <div className="space-y-5">
            {/* Tab bar */}
            <div className="flex border-b border-gray-200 bg-white rounded-t-xl px-4 pt-4 -mb-5 overflow-hidden">
              {(['document', 'claims', 'history'] as ActiveTab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab
                      ? 'border-gray-900 text-gray-900'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {tab === 'document' ? 'Document Sections' : tab === 'claims' ? 'Claims' : 'File History'}
                </button>
              ))}
            </div>

            {/* Document Sections */}
            {activeTab === 'document' && (
              <div className="space-y-4 pt-2">
                {sections.map((section) => (
                  <div
                    key={section.key}
                    className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden"
                  >
                    <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-gray-50">
                      <h3 className="text-sm font-semibold text-gray-800">{section.label}</h3>
                      {editingSection !== section.key && (
                        <button
                          onClick={() => startEdit(section.key, section.content)}
                          className="text-xs text-gray-500 hover:text-gray-800 font-medium px-2 py-1 rounded hover:bg-gray-100 transition-colors"
                        >
                          Edit
                        </button>
                      )}
                    </div>
                    <div className="px-5 py-4">
                      {editingSection === section.key ? (
                        <div className="space-y-3">
                          <textarea
                            rows={section.key === 'specification' ? 12 : 5}
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 resize-y"
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => saveEdit(section.key)}
                              className="px-3 py-1.5 bg-gray-900 text-white text-xs font-medium rounded-lg hover:bg-gray-800 transition-colors"
                            >
                              Save
                            </button>
                            <button
                              onClick={cancelEdit}
                              className="px-3 py-1.5 border border-gray-300 text-gray-600 text-xs font-medium rounded-lg hover:bg-gray-50 transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                          {section.content || <span className="text-gray-400 italic">No content</span>}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Claims */}
            {activeTab === 'claims' && (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 pt-8">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-base font-semibold text-gray-900">Claims Hierarchy</h3>
                  <span className="text-sm text-gray-400">
                    {draft.claims?.length ?? 0} claim{(draft.claims?.length ?? 0) !== 1 ? 's' : ''}
                  </span>
                </div>
                <ClaimsTree claims={draft.claims ?? []} />
              </div>
            )}

            {/* File History */}
            {activeTab === 'history' && (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 pt-8">
                <h3 className="text-base font-semibold text-gray-900 mb-5">File History</h3>
                <FileHistory entries={draft.history ?? []} />
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
