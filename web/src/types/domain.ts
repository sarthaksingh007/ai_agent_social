/**
 * Mirrors the Pydantic contracts in `src/schemas.py`. Keep these in sync —
 * the backend validates on its side, these types only guard the UI.
 */

export type Platform = 'instagram' | 'linkedin' | 'twitter' | 'facebook' | 'tiktok'

export type PostStatus =
  | 'Pending Human Review'
  | 'Approved'
  | 'Rejected'
  | 'Published'

export type JobStatus = 'queued' | 'running' | 'done' | 'failed'

/** The six agents, in pipeline order. */
export type AgentName =
  | 'Account Manager'
  | 'Strategist'
  | 'Validator'
  | 'Project Manager'
  | 'Copywriter'
  | 'Designer'

export interface BrandDossier {
  client_name: string
  industry: string
  target_audience: string
  brand_voice: string
  target_platforms: Platform[]
  goals: string[]
  kpis: string[]
  key_products: string[]
  known_competitors: string[]
  insufficient_context: boolean
  missing_fields: string[]
}

export interface ContentPillar {
  pillar_name: string
  justification: string
  evidence_urls: string[]
}

export interface PostStructure {
  date: string
  platform: Platform[]
  pillar: string
  angle_and_objective: string
}

export interface Strategy {
  client_name: string
  competitor_urls_scanned: string[]
  market_trends_discovered: string[]
  content_pillars: ContentPillar[]
  one_month_calendar_skeleton: PostStructure[]
}

export interface DimensionCheck {
  dimension: string
  passed: boolean
  reason: string
  hard: boolean
}

export interface ValidationResult {
  approved: boolean
  checks: DimensionCheck[]
  correction_notes: string[]
  missing_citations: string[]
}

export interface WeeklyPlan {
  week_number: number
  theme: string
  posts: PostStructure[]
}

export interface PlatformVariant {
  platform: Platform
  body_caption: string
  hashtags: string[]
}

export type ContentFormat = 'post' | 'carousel' | 'reel'

export interface CarouselSlide {
  slide_no: number
  headline: string
  caption: string
  visual_generation_prompt: string
  image_path: string | null
}

export interface ReelScene {
  shot: string
  on_screen_text: string
  voiceover: string
}

export interface ReelScript {
  hook: string
  scenes: ReelScene[]
  cta: string
  audio_suggestion: string
  duration_seconds: number
  cover_prompt: string
}

/** A Copywriter draft, before it becomes a row in `posts`. */
export interface Draft {
  post_id: string
  client_name: string
  scheduled_date: string
  target_platforms: Platform[]
  pillar: string
  content_format: ContentFormat
  hook_text: string
  body_caption: string
  hashtags: string[]
  cta_text: string
  visual_generation_prompt: string
  platform_variants: PlatformVariant[]
  carousel_slides: CarouselSlide[]
  reel_script: ReelScript | null
  image_path: string | null
  image_variants: string[]
  status: PostStatus
}

/** A persisted post row, enriched by the API with browser-fetchable URLs. */
export interface Post {
  post_id: string
  project_id: number | null
  client_name: string
  scheduled_date: string | null
  target_platforms: Platform[] | null
  pillar: string | null
  hook_text: string | null
  body_caption: string | null
  hashtags: string[] | null
  cta_text: string | null
  visual_prompt: string | null
  platform_variants: PlatformVariant[] | null
  image_path: string | null
  image_variants: string[] | null
  image_url: string | null
  image_variant_urls: { path: string; url: string }[]
  status: PostStatus
  created_at: string
}

export interface BrandKit {
  client_name: string
  colors: string[]
  font_style: string
  logo_description: string
  handle: string
  website: string
  style_notes: string
}

export interface Job {
  id: number
  project_id: number
  project_name: string
  job_type: string
  label: string
  agent: string
  status: JobStatus
  error: string | null
  created_at: string
}

export interface Project {
  id: number
  name: string
  state: WizardState
  created_at: string
  updated_at: string
}

export type WizardStage =
  | 'brief'
  | 'dossier'
  | 'strategy'
  | 'weekly'
  | 'copy'
  | 'design'

/** Free-form JSON blob the worker also writes into — every field optional. */
/** Structured inputs for the Account Manager, entered via the Brief form.
 * Composed into the free-text `brief` string before enqueuing. */
export interface BriefForm {
  brand?: string
  industry?: string
  products?: string
  audience?: string
  voice?: string
  platforms?: string[]
  goals?: string
  notes?: string
}

export interface WizardState {
  stage?: WizardStage
  brief?: string
  /** How the brief was last entered — drives which input the Brief step shows. */
  briefMode?: 'form' | 'text'
  briefForm?: BriefForm
  dossier?: BrandDossier
  strategy?: Strategy | null
  validation?: ValidationResult | null
  weeks?: WeeklyPlan[]
  /** Format chosen for the next Copywriter run (post / carousel / reel). */
  copyFormat?: ContentFormat
  drafts?: Draft[] | null
}

export interface WorkerStatus {
  running: Job | null
  active_agent: string | null
  queue_depth: number
}

export interface AppConfig {
  agents: AgentName[]
  models: Record<string, string>
  sample_brief: string
  problems: string[]
}
