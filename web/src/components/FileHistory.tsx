
export type ActionType =
  | 'created'
  | 'search_run'
  | 'analysis_complete'
  | 'draft_generated'
  | 'reviewed'
  | 'exported'
  | 'edited'
  | 'filed'
  | 'error';

export interface HistoryEntry {
  id: string;
  action: ActionType;
  description: string;
  timestamp: string;
  user?: string;
  metadata?: Record<string, unknown>;
}

interface FileHistoryProps {
  entries: HistoryEntry[];
}

const ACTION_ICONS: Record<ActionType, { icon: string; style: string }> = {
  created: { icon: 'C', style: 'bg-blue-100 text-blue-700' },
  search_run: { icon: 'S', style: 'bg-purple-100 text-purple-700' },
  analysis_complete: { icon: 'A', style: 'bg-indigo-100 text-indigo-700' },
  draft_generated: { icon: 'D', style: 'bg-cyan-100 text-cyan-700' },
  reviewed: { icon: 'R', style: 'bg-yellow-100 text-yellow-700' },
  exported: { icon: 'E', style: 'bg-green-100 text-green-700' },
  edited: { icon: 'Ed', style: 'bg-orange-100 text-orange-700' },
  filed: { icon: 'F', style: 'bg-green-100 text-green-800' },
  error: { icon: 'X', style: 'bg-red-100 text-red-700' },
};

const ACTION_LABELS: Record<ActionType, string> = {
  created: 'Project Created',
  search_run: 'Prior Art Search',
  analysis_complete: 'Analysis Complete',
  draft_generated: 'Draft Generated',
  reviewed: 'Review Complete',
  exported: 'Exported',
  edited: 'Edited',
  filed: 'Filed',
  error: 'Error',
};

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return ts;
  }
}

export function FileHistory({ entries }: FileHistoryProps) {
  if (entries.length === 0) {
    return (
      <div className="text-sm text-gray-400 text-center py-8">No history available.</div>
    );
  }

  const sorted = [...entries].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  return (
    <ol className="relative border-l border-gray-200 ml-3">
      {sorted.map((entry, i) => {
        const config = ACTION_ICONS[entry.action] ?? { icon: '?', style: 'bg-gray-100 text-gray-600' };
        const label = ACTION_LABELS[entry.action] ?? entry.action;
        return (
          <li key={entry.id} className={`ml-6 ${i < sorted.length - 1 ? 'mb-6' : ''}`}>
            <span
              className={`absolute -left-3.5 flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${config.style}`}
            >
              {config.icon}
            </span>
            <div className="p-3 bg-white rounded-lg border border-gray-100 shadow-sm">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-gray-800">{label}</p>
                <time className="text-xs text-gray-400 shrink-0">
                  {formatTimestamp(entry.timestamp)}
                </time>
              </div>
              <p className="mt-1 text-sm text-gray-600 leading-relaxed">{entry.description}</p>
              {entry.user && (
                <p className="mt-1 text-xs text-gray-400">by {entry.user}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
