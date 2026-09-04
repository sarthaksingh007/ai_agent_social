/** Single source of truth for cache keys, so invalidation never guesses. */
export const qk = {
  config: ['config'] as const,
  status: ['status'] as const,
  projects: ['projects'] as const,
  project: (id: number) => ['projects', id] as const,
  jobs: (id: number) => ['projects', id, 'jobs'] as const,
  posts: (id: number) => ['projects', id, 'posts'] as const,
  brandKit: (client: string) => ['brand-kits', client] as const,
}
