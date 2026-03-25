import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { usePatentSearch, type SearchResult } from '../hooks/usePatentSearch';
import { PatentCard } from '../components/PatentCard';
import { ComparisonTable, type ComparisonRow } from '../components/ComparisonTable';

type SortField = 'relevance' | 'date' | 'severity';
type FilterSeverity = 'all' | 'clear' | 'caution' | 'conflict';

function buildComparisonRows(selected: SearchResult): ComparisonRow[] {
  if (!selected.overlap_features || selected.overlap_features.length === 0) return [];
  return selected.overlap_features.map((feature) => ({
    feature,
    invention: 'Present in claimed invention',
    prior_art: `Disclosed in ${selected.patent_number}`,
    overlap: selected.severity === 'conflict' ? 'full' : selected.severity === 'caution' ? 'partial' : 'none',
  }));
}

export function SearchResults() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { loading, results, error, search } = usePatentSearch();

  const [sortBy, setSortBy] = useState<SortField>('relevance');
  const [filterSeverity, setFilterSeverity] = useState<FilterSeverity>('all');
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null);

  useEffect(() => {
    if (projectId) {
      search({ description: '', project_id: projectId });
    }
  }, [projectId, search]);

  const filtered = results
    .filter((r) => filterSeverity === 'all' || r.severity === filterSeverity)
    .sort((a, b) => {
      if (sortBy === 'relevance') return (b.relevance_score ?? 0) - (a.relevance_score ?? 0);
      if (sortBy === 'date') return new Date(b.filing_date).getTime() - new Date(a.filing_date).getTime();
      if (sortBy === 'severity') {
        const order = { conflict: 0, caution: 1, clear: 2 };
        return (order[a.severity ?? 'clear'] ?? 2) - (order[b.severity ?? 'clear'] ?? 2);
      }
      return 0;
    });

  const comparisonRows = selectedResult ? buildComparisonRows(selectedResult) : [];

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-14 gap-4">
            <button
              onClick={() => navigate('/')}
              className="text-sm text-gray-500 hover:text-gray-900"
            >
              &larr; Dashboard
            </button>
            <h1 className="text-base font-semibold text-gray-900">Prior Art Search Results</h1>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Controls */}
        <div className="flex flex-wrap gap-3 mb-5 items-center">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Filter:</label>
            <select
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value as FilterSeverity)}
              className="text-sm border border-gray-300 rounded-lg px-2.5 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-gray-900"
            >
              <option value="all">All Severities</option>
              <option value="clear">Clear</option>
              <option value="caution">Caution</option>
              <option value="conflict">Conflict</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Sort:</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortField)}
              className="text-sm border border-gray-300 rounded-lg px-2.5 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-gray-900"
            >
              <option value="relevance">Relevance</option>
              <option value="date">Filing Date</option>
              <option value="severity">Severity</option>
            </select>
          </div>
          <span className="text-sm text-gray-400 ml-auto">
            {filtered.length} result{filtered.length !== 1 ? 's' : ''}
          </span>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin w-6 h-6 border-2 border-gray-300 border-t-gray-900 rounded-full" />
            <span className="ml-3 text-sm text-gray-500">Loading search results...</span>
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-4 mb-5">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
            <p className="text-sm text-gray-500">No prior art results found matching the current filters.</p>
          </div>
        )}

        {!loading && filtered.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 mb-8">
            {filtered.map((r) => (
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
                onClick={() => setSelectedResult(r === selectedResult ? null : r)}
              />
            ))}
          </div>
        )}

        {selectedResult && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-gray-900">
                Feature Comparison: {selectedResult.patent_number}
              </h2>
              <button
                onClick={() => setSelectedResult(null)}
                className="text-sm text-gray-400 hover:text-gray-700"
              >
                Close
              </button>
            </div>
            {comparisonRows.length > 0 ? (
              <ComparisonTable rows={comparisonRows} priorArtTitle={selectedResult.patent_number} />
            ) : (
              <p className="text-sm text-gray-400">No detailed overlap data available for this patent.</p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
