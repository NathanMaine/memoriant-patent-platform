import { useState } from 'react';

export interface Claim {
  number: number;
  text: string;
  type: 'independent' | 'dependent';
  depends_on?: number;
}

interface ClaimsTreeProps {
  claims: Claim[];
}

interface ClaimNodeProps {
  claim: Claim;
  dependents: Claim[];
  allClaims: Claim[];
  depth: number;
}

function ClaimNode({ claim, dependents, allClaims, depth }: ClaimNodeProps) {
  const [expanded, setExpanded] = useState(true);
  const hasDependents = dependents.length > 0;

  return (
    <div className={depth > 0 ? 'ml-6 border-l border-gray-200 pl-4' : ''}>
      <div className="flex items-start gap-3 py-2.5 group">
        {hasDependents ? (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-0.5 shrink-0 w-5 h-5 flex items-center justify-center text-gray-400 hover:text-gray-600 rounded"
            aria-label={expanded ? 'Collapse' : 'Expand'}
          >
            <svg
              className={`w-3 h-3 transition-transform ${expanded ? 'rotate-90' : ''}`}
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        ) : (
          <span className="mt-0.5 shrink-0 w-5 h-5" />
        )}

        <div className="flex items-start gap-2 flex-1 min-w-0">
          <span
            className={`shrink-0 mt-0.5 text-xs font-bold px-2 py-0.5 rounded ${
              claim.type === 'independent'
                ? 'bg-blue-100 text-blue-800'
                : 'bg-gray-100 text-gray-600'
            }`}
          >
            {claim.number}
          </span>
          <p className="text-sm text-gray-800 leading-relaxed">{claim.text}</p>
        </div>
      </div>

      {expanded && hasDependents && (
        <div>
          {dependents.map((dep) => (
            <ClaimNode
              key={dep.number}
              claim={dep}
              dependents={allClaims.filter((c) => c.depends_on === dep.number)}
              allClaims={allClaims}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function ClaimsTree({ claims }: ClaimsTreeProps) {
  if (claims.length === 0) {
    return (
      <div className="text-sm text-gray-400 text-center py-8">No claims available.</div>
    );
  }

  const independentClaims = claims.filter((c) => c.type === 'independent');

  return (
    <div className="divide-y divide-gray-50">
      {independentClaims.map((claim) => (
        <ClaimNode
          key={claim.number}
          claim={claim}
          dependents={claims.filter((c) => c.depends_on === claim.number)}
          allClaims={claims}
          depth={0}
        />
      ))}
    </div>
  );
}
