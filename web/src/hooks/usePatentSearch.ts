import { useState, useCallback } from 'react';
import { api } from '../services/api';

export interface SearchResult {
  patent_number: string;
  title: string;
  abstract: string;
  inventors: string[];
  filing_date: string;
  assignee?: string;
  relevance_score?: number;
  overlap_features?: string[];
  severity?: 'clear' | 'caution' | 'conflict';
}

interface SearchQuery {
  description: string;
  technical_field?: string;
  project_id?: string;
}

export function usePatentSearch() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const search = useCallback(async (query: SearchQuery) => {
    setLoading(true);
    setError(null);
    setSearched(false);
    try {
      const data = await api.search(query) as { results: SearchResult[] };
      setResults(data.results ?? []);
      setSearched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const clear = useCallback(() => {
    setResults([]);
    setError(null);
    setSearched(false);
  }, []);

  return { loading, results, error, searched, search, clear };
}
