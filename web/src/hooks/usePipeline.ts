import { useState, useEffect } from 'react';
import { supabase } from '../services/supabase';

export type PipelineStatus = 'idle' | 'running' | 'completed' | 'failed';

export interface PipelineState {
  stage: string;
  progress: number;
  status: PipelineStatus;
  error: string | null;
  runId: string | null;
}

const INITIAL_STATE: PipelineState = {
  stage: '',
  progress: 0,
  status: 'idle',
  error: null,
  runId: null,
};

export function usePipeline(projectId?: string) {
  const [pipeline, setPipeline] = useState<PipelineState>(INITIAL_STATE);

  useEffect(() => {
    if (!projectId) return;

    const channel = supabase
      .channel(`pipeline_runs:${projectId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'pipeline_runs',
          filter: `project_id=eq.${projectId}`,
        },
        (payload) => {
          const row = payload.new as Record<string, unknown>;
          setPipeline({
            stage: (row.stage as string) ?? '',
            progress: (row.progress as number) ?? 0,
            status: (row.status as PipelineStatus) ?? 'idle',
            error: (row.error as string) ?? null,
            runId: (row.id as string) ?? null,
          });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [projectId]);

  const reset = () => setPipeline(INITIAL_STATE);

  return { ...pipeline, reset };
}
