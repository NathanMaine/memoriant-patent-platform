import React from 'react';

export type StepStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface PipelineStep {
  key: string;
  label: string;
  status: StepStatus;
}

interface PipelineProgressProps {
  steps: PipelineStep[];
  progress?: number;
  currentStage?: string;
}

function CheckIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function StepIcon({ status, index }: { status: StepStatus; index: number }) {
  if (status === 'completed') {
    return (
      <span className="flex items-center justify-center w-8 h-8 rounded-full bg-green-600 text-white">
        <CheckIcon />
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span className="flex items-center justify-center w-8 h-8 rounded-full bg-red-600 text-white">
        <XIcon />
      </span>
    );
  }
  if (status === 'running') {
    return (
      <span className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-600 text-white animate-pulse">
        <span className="text-xs font-bold">{index + 1}</span>
      </span>
    );
  }
  return (
    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-gray-200 text-gray-500">
      <span className="text-xs font-medium">{index + 1}</span>
    </span>
  );
}

export function PipelineProgress({ steps, progress, currentStage }: PipelineProgressProps) {
  return (
    <div className="w-full">
      <div className="flex items-center">
        {steps.map((step, i) => (
          <React.Fragment key={step.key}>
            <div className="flex flex-col items-center">
              <StepIcon status={step.status} index={i} />
              <span
                className={`mt-1.5 text-xs font-medium text-center max-w-[72px] leading-tight ${
                  step.status === 'completed'
                    ? 'text-green-700'
                    : step.status === 'running'
                    ? 'text-blue-700'
                    : step.status === 'failed'
                    ? 'text-red-700'
                    : 'text-gray-400'
                }`}
              >
                {step.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={`flex-1 h-0.5 mx-1 mb-5 ${
                  steps[i + 1].status === 'completed' || step.status === 'completed'
                    ? 'bg-green-400'
                    : step.status === 'running'
                    ? 'bg-blue-200'
                    : 'bg-gray-200'
                }`}
              />
            )}
          </React.Fragment>
        ))}
      </div>

      {(progress !== undefined || currentStage) && (
        <div className="mt-4">
          {currentStage && (
            <p className="text-sm text-gray-600 mb-1">
              Current stage: <span className="font-medium text-gray-800">{currentStage}</span>
            </p>
          )}
          {progress !== undefined && (
            <div className="w-full bg-gray-100 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
              />
            </div>
          )}
          {progress !== undefined && (
            <p className="text-xs text-gray-500 mt-1 text-right">{Math.round(progress)}%</p>
          )}
        </div>
      )}
    </div>
  );
}
