/**
 * Shared wizard plumbing.
 *
 * The project's `state` blob is the single source of truth and it has two
 * writers: this UI, and the worker (which merges agent results into it). So a
 * save always merges a patch onto the freshest state we've fetched rather than
 * PUTting a whole locally-held object — otherwise a save typed during a run
 * would wipe out whatever the worker just wrote.
 */
import { useCallback } from 'react'

import { useEnqueueJob, useSaveState } from '@/api/hooks'
import { useToast } from '@/components/feedback/ToastProvider'
import type { Project, WizardStage, WizardState } from '@/types/domain'

export const STAGES: WizardStage[] = [
  'brief',
  'dossier',
  'strategy',
  'weekly',
  'copy',
  'design',
]

export const STAGE_LABELS: Record<WizardStage, string> = {
  brief: '① Brief',
  dossier: '② Dossier',
  strategy: '③ Strategy',
  weekly: '④ Weekly',
  copy: '⑤ Copy',
  design: '⑥ Design',
}

export function useWizard(project: Project) {
  const state: WizardState = project.state ?? {}
  const stage: WizardStage = state.stage ?? 'brief'

  const saveMutation = useSaveState(project.id)
  const enqueueMutation = useEnqueueJob(project.id)
  const { toast } = useToast()

  const patchState = useCallback(
    (patch: Partial<WizardState>) => saveMutation.mutate({ ...state, ...patch }),
    [saveMutation, state],
  )

  const goToStage = useCallback((next: WizardStage) => patchState({ stage: next }), [patchState])

  const reset = useCallback(() => saveMutation.mutate({}), [saveMutation])

  const enqueue = useCallback(
    (jobType: string, payload: Record<string, unknown>, label: string) =>
      enqueueMutation.mutate(
        { job_type: jobType, payload, label },
        {
          onSuccess: () => toast(`Queued: ${label}`),
          onError: (err) => toast(err.message, 'error'),
        },
      ),
    [enqueueMutation, toast],
  )

  return {
    state,
    stage,
    patchState,
    goToStage,
    reset,
    enqueue,
    isSaving: saveMutation.isPending,
    isEnqueuing: enqueueMutation.isPending,
  }
}

export type Wizard = ReturnType<typeof useWizard>
