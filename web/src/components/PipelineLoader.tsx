import { useEffect, useState } from 'react';
import { SkeletonCard } from './SkeletonCard';

const STAGE_ESTIMATES: Record<string, number> = {
  search: 30,
  analyze: 45,
  draft: 60,
  review: 30,
  export: 10,
};

const DEFAULT_ESTIMATE = 30;

interface PipelineLoaderProps {
  stageName: string;
  stagesCompleted: number;
  totalStages: number;
}

function SpinnerIcon() {
  return (
    <svg
      className="animate-spin w-5 h-5 text-blue-600"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

export function PipelineLoader({ stageName, stagesCompleted, totalStages }: PipelineLoaderProps) {
  const stageKey = stageName.toLowerCase();
  const estimatedSeconds = STAGE_ESTIMATES[stageKey] ?? DEFAULT_ESTIMATE;

  const [secondsElapsed, setSecondsElapsed] = useState(0);

  useEffect(() => {
    setSecondsElapsed(0);
    const interval = setInterval(() => {
      setSecondsElapsed((prev) => {
        if (prev >= estimatedSeconds) {
          clearInterval(interval);
          return prev;
        }
        return prev + 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [stageName, estimatedSeconds]);

  const secondsRemaining = Math.max(0, estimatedSeconds - secondsElapsed);
  const progressPercent =
    totalStages > 0
      ? Math.round(((stagesCompleted + secondsElapsed / estimatedSeconds) / totalStages) * 100)
      : 0;
  const clampedProgress = Math.min(100, Math.max(0, progressPercent));

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `~${seconds}s`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `~${m}m ${s > 0 ? `${s}s` : ''}`.trim();
  };

  return (
    <div className="w-full space-y-4">
      {/* Stage indicator */}
      <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg border border-blue-100 animate-pulse">
        <SpinnerIcon />
        <div className="flex-1">
          <p className="text-sm font-semibold text-blue-800 capitalize">{stageName}</p>
          <p className="text-xs text-blue-600">
            {secondsRemaining > 0
              ? `Estimated time remaining: ${formatTime(secondsRemaining)}`
              : 'Finishing up…'}
          </p>
        </div>
        <span className="text-xs font-medium text-blue-700">
          {stagesCompleted}/{totalStages} stages
        </span>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Overall progress</span>
          <span>{clampedProgress}%</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-1000"
            style={{ width: `${clampedProgress}%` }}
          />
        </div>
      </div>

      {/* Skeleton cards for loading content */}
      <div className="space-y-3 mt-2">
        <SkeletonCard lines={2} />
        <SkeletonCard lines={3} />
        <SkeletonCard lines={2} />
      </div>
    </div>
  );
}

export default PipelineLoader;
