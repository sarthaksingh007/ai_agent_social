/**
 * Server-state layer. Every network call the app makes lives here as a hook;
 * components never touch `http` directly.
 *
 * Polling: the worker runs jobs out-of-band, so `useWorkerStatus` polls while
 * anything is queued or running and goes quiet when the queue drains. Job and
 * post lists follow the same signal via `usePollWhileBusy`.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { http } from '@/lib/http'
import type {
  AppConfig,
  BrandKit,
  Job,
  Post,
  PostStatus,
  Project,
  WizardState,
  WorkerStatus,
} from '@/types/domain'

import { qk } from './queryKeys'

const POLL_MS = 2500

/* --------------------------------- meta --------------------------------- */

export function useConfig() {
  return useQuery({
    queryKey: qk.config,
    queryFn: () => http.get<AppConfig>('/api/config'),
    staleTime: Infinity,
  })
}

export function useWorkerStatus() {
  return useQuery({
    queryKey: qk.status,
    queryFn: () => http.get<WorkerStatus>('/api/status'),
    // Keep polling while work is in flight; idle otherwise.
    refetchInterval: (query) => {
      const data = query.state.data
      return data && (data.running || data.queue_depth > 0) ? POLL_MS : false
    },
    refetchIntervalInBackground: false,
  })
}

/** True while the worker has anything queued or running. */
export function useIsBusy(): boolean {
  const { data } = useWorkerStatus()
  return Boolean(data && (data.running || data.queue_depth > 0))
}

/* ------------------------------- projects ------------------------------- */

export function useProjects() {
  return useQuery({
    queryKey: qk.projects,
    queryFn: () => http.get<Project[]>('/api/projects'),
  })
}

export function useProject(projectId: number | null) {
  const busy = useIsBusy()
  return useQuery({
    queryKey: qk.project(projectId!),
    queryFn: () => http.get<Project>(`/api/projects/${projectId}`),
    enabled: projectId !== null,
    // The worker writes agent results straight into project.state.
    refetchInterval: busy ? POLL_MS : false,
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => http.post<Project>('/api/projects', { name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.projects }),
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (projectId: number) => http.del<void>(`/api/projects/${projectId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.projects }),
  })
}

export function useSaveState(projectId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (state: WizardState) =>
      http.put<{ ok: boolean }>(`/api/projects/${projectId}/state`, { state }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.project(projectId) }),
  })
}

/* --------------------------------- jobs --------------------------------- */

export function useJobs(projectId: number | null) {
  const busy = useIsBusy()
  return useQuery({
    queryKey: qk.jobs(projectId!),
    queryFn: () => http.get<Job[]>(`/api/projects/${projectId}/jobs`),
    enabled: projectId !== null,
    refetchInterval: busy ? POLL_MS : false,
  })
}

export interface EnqueueArgs {
  job_type: string
  payload: Record<string, unknown>
  label: string
}

export function useEnqueueJob(projectId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: EnqueueArgs) =>
      http.post<{ id: number }>(`/api/projects/${projectId}/jobs`, args),
    onSuccess: () => {
      // Wake the status poll immediately rather than waiting for the interval.
      qc.invalidateQueries({ queryKey: qk.status })
      qc.invalidateQueries({ queryKey: qk.jobs(projectId) })
    },
  })
}

/* --------------------------------- posts -------------------------------- */

export function usePosts(projectId: number | null) {
  const busy = useIsBusy()
  return useQuery({
    queryKey: qk.posts(projectId!),
    queryFn: () => http.get<Post[]>(`/api/projects/${projectId}/posts`),
    enabled: projectId !== null,
    refetchInterval: busy ? POLL_MS : false,
  })
}

export interface PostPatch {
  status?: PostStatus
  hook_text?: string
  body_caption?: string
  image_path?: string
}

export function usePatchPost(projectId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ postId, patch }: { postId: string; patch: PostPatch }) =>
      http.patch<{ ok: boolean }>(`/api/posts/${postId}`, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.posts(projectId) }),
  })
}

export function usePublishPost(projectId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (postId: string) =>
      http.post<{ sent_via: string }>(`/api/posts/${postId}/publish`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.posts(projectId) }),
  })
}

/* ------------------------------ brand kits ------------------------------ */

export function useBrandKit(clientName: string) {
  return useQuery({
    queryKey: qk.brandKit(clientName),
    queryFn: () =>
      http.get<Partial<BrandKit>>(`/api/brand-kits/${encodeURIComponent(clientName)}`),
    enabled: clientName.trim().length > 0,
  })
}

export function useSaveBrandKit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (kit: BrandKit) => http.put<{ ok: boolean }>('/api/brand-kits', kit),
    onSuccess: (_data, kit) =>
      qc.invalidateQueries({ queryKey: qk.brandKit(kit.client_name) }),
  })
}
