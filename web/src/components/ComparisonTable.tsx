
export type OverlapLevel = 'none' | 'partial' | 'full';

export interface ComparisonRow {
  feature: string;
  invention: string;
  prior_art: string;
  overlap: OverlapLevel;
}

interface ComparisonTableProps {
  rows: ComparisonRow[];
  priorArtTitle?: string;
}

const OVERLAP_STYLES: Record<OverlapLevel, string> = {
  none: 'bg-green-50',
  partial: 'bg-yellow-50',
  full: 'bg-red-50',
};

const OVERLAP_BADGE: Record<OverlapLevel, { label: string; style: string }> = {
  none: { label: 'No Overlap', style: 'bg-green-100 text-green-800' },
  partial: { label: 'Partial Overlap', style: 'bg-yellow-100 text-yellow-800' },
  full: { label: 'Full Overlap', style: 'bg-red-100 text-red-800' },
};

export function ComparisonTable({ rows, priorArtTitle }: ComparisonTableProps) {
  if (rows.length === 0) {
    return (
      <div className="text-sm text-gray-400 text-center py-8">
        No comparison data available.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left font-semibold text-gray-700 w-1/4">Feature</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-700 w-1/3">
              Your Invention
            </th>
            <th className="px-4 py-3 text-left font-semibold text-gray-700 w-1/3">
              {priorArtTitle ?? 'Prior Art'}
            </th>
            <th className="px-4 py-3 text-left font-semibold text-gray-700 w-36">
              Overlap
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-100">
          {rows.map((row, i) => {
            const badge = OVERLAP_BADGE[row.overlap];
            return (
              <tr key={i} className={OVERLAP_STYLES[row.overlap]}>
                <td className="px-4 py-3 font-medium text-gray-800 align-top">{row.feature}</td>
                <td className="px-4 py-3 text-gray-700 align-top leading-relaxed">
                  {row.invention}
                </td>
                <td className="px-4 py-3 text-gray-700 align-top leading-relaxed">
                  {row.prior_art}
                </td>
                <td className="px-4 py-3 align-top">
                  <span className={`inline-block text-xs font-medium px-2 py-1 rounded-full ${badge.style}`}>
                    {badge.label}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
