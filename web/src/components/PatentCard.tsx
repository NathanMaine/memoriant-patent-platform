import React from 'react';

export type PatentStatus = 'draft' | 'in_progress' | 'filed' | 'granted' | 'abandoned' | 'clear' | 'caution' | 'conflict';

export interface PatentCardData {
  id?: string;
  patent_number?: string;
  title: string;
  abstract?: string;
  inventors?: string[];
  filing_date?: string;
  created_at?: string;
  status?: PatentStatus;
  filing_format?: string;
  nonprovisional_deadline?: string;
  assignee?: string;
  relevance_score?: number;
}

interface PatentCardProps {
  patent: PatentCardData;
  onClick?: () => void;
}

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  in_progress: 'bg-yellow-100 text-yellow-800',
  filed: 'bg-blue-100 text-blue-800',
  granted: 'bg-green-100 text-green-800',
  abandoned: 'bg-red-100 text-red-800',
  clear: 'bg-green-100 text-green-800',
  caution: 'bg-yellow-100 text-yellow-800',
  conflict: 'bg-red-100 text-red-800',
};

const STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  in_progress: 'In Progress',
  filed: 'Filed',
  granted: 'Granted',
  abandoned: 'Abandoned',
  clear: 'Clear',
  caution: 'Caution',
  conflict: 'Conflict',
};

function formatDate(dateStr?: string): string {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

export function PatentCard({ patent, onClick }: PatentCardProps) {
  const status = patent.status ?? 'draft';
  const statusStyle = STATUS_STYLES[status] ?? STATUS_STYLES.draft;
  const statusLabel = STATUS_LABELS[status] ?? status;
  const displayDate = patent.filing_date ?? patent.created_at;

  return (
    <div
      className={`bg-white rounded-lg border border-gray-200 shadow-sm p-5 transition-shadow ${onClick ? 'cursor-pointer hover:shadow-md' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === 'Enter' && onClick() : undefined}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-semibold text-gray-900 truncate">{patent.title}</h3>
          {patent.patent_number && (
            <p className="text-xs text-gray-400 mt-0.5 font-mono">{patent.patent_number}</p>
          )}
        </div>
        <span className={`shrink-0 text-xs font-medium px-2.5 py-1 rounded-full ${statusStyle}`}>
          {statusLabel}
        </span>
      </div>

      {patent.abstract && (
        <p className="mt-3 text-sm text-gray-600 line-clamp-3 leading-relaxed">
          {patent.abstract}
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
        {patent.inventors && patent.inventors.length > 0 && (
          <span>
            {patent.inventors.slice(0, 2).join(', ')}
            {patent.inventors.length > 2 ? ` +${patent.inventors.length - 2} more` : ''}
          </span>
        )}
        {patent.assignee && <span>{patent.assignee}</span>}
        {displayDate && <span>{formatDate(displayDate)}</span>}
        {patent.filing_format && (
          <span className="font-medium text-gray-600">{patent.filing_format}</span>
        )}
        {patent.relevance_score !== undefined && (
          <span>Relevance: {Math.round(patent.relevance_score * 100)}%</span>
        )}
      </div>

      {patent.nonprovisional_deadline && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p className="text-xs text-amber-700 font-medium">
            Nonprovisional deadline: {formatDate(patent.nonprovisional_deadline)}
          </p>
        </div>
      )}
    </div>
  );
}
