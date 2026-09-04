import { useState } from 'react'

import { useConfig } from '@/api/hooks'
import { IconPlay } from '@/components/icons'
import { Button, Card, Field, Input, Textarea } from '@/components/ui'
import type { BriefForm } from '@/types/domain'

import type { Wizard } from '../useWizard'

const PLATFORMS = ['instagram', 'linkedin', 'twitter', 'facebook', 'tiktok']

/** Turn the structured form into the free-text brief the Account Manager reads.
 * Only non-empty fields are emitted, so a sparse form stays readable. */
function composeBrief(f: BriefForm): string {
  const lines: [string, string | undefined][] = [
    ['Brand', f.brand],
    ['Industry / niche', f.industry],
    ['Products / services', f.products],
    ['Target audience', f.audience],
    ['Brand voice', f.voice],
    ['Platforms', f.platforms?.join(', ')],
    ['Goals', f.goals],
    ['Additional notes', f.notes],
  ]
  return lines
    .filter(([, v]) => v && v.trim())
    .map(([k, v]) => `${k}: ${v!.trim()}`)
    .join('\n')
}

export function BriefStep({ wizard }: { wizard: Wizard }) {
  const { data: config } = useConfig()
  const [mode, setMode] = useState<'form' | 'text'>(wizard.state.briefMode ?? 'form')
  const [form, setForm] = useState<BriefForm>(() => wizard.state.briefForm ?? {})
  const [brief, setBrief] = useState(
    () => wizard.state.brief ?? config?.sample_brief ?? '',
  )

  const set = (key: keyof BriefForm, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }))

  const togglePlatform = (p: string) =>
    setForm((prev) => {
      const current = prev.platforms ?? []
      const platforms = current.includes(p)
        ? current.filter((x) => x !== p)
        : [...current, p]
      return { ...prev, platforms }
    })

  // In form mode the brief is composed from the fields; in text mode it's typed.
  const composed = composeBrief(form)
  const effectiveBrief = mode === 'form' ? composed : brief
  const canRun = mode === 'form' ? Boolean(form.brand?.trim()) : Boolean(brief.trim())

  const run = () => {
    wizard.patchState({ brief: effectiveBrief, briefMode: mode, briefForm: form })
    wizard.enqueue('dossier', { brief: effectiveBrief }, 'Account Manager → dossier')
  }

  return (
    <Card title="Client brief">
      <div className="row row--between" style={{ marginBottom: 16 }}>
        <div className="row" role="tablist" aria-label="Brief input mode">
          <Button
            size="sm"
            variant={mode === 'form' ? 'primary' : 'ghost'}
            onClick={() => setMode('form')}
          >
            Form
          </Button>
          <Button
            size="sm"
            variant={mode === 'text' ? 'primary' : 'ghost'}
            onClick={() => setMode('text')}
          >
            Free text
          </Button>
        </div>
      </div>

      {mode === 'form' ? (
        <>
          <div className="grid-2">
            <Field
              label="Brand / client name"
              hint="Required. The official brand name. Example: Bean There"
            >
              <Input
                value={form.brand ?? ''}
                onChange={(e) => set('brand', e.target.value)}
                placeholder="e.g. Bean There"
              />
            </Field>
            <Field
              label="Industry / niche"
              hint="What the brand does / its category. Example: independent vegan coffee shop in Mumbai"
            >
              <Input
                value={form.industry ?? ''}
                onChange={(e) => set('industry', e.target.value)}
                placeholder="e.g. Vegan coffee shop"
              />
            </Field>
            <Field
              label="Products / services"
              hint="Main things to feature, comma-separated. Example: house-roasted beans, vegan pastries, cold brew"
            >
              <Input
                value={form.products ?? ''}
                onChange={(e) => set('products', e.target.value)}
                placeholder="e.g. house-roasted beans, vegan pastries"
              />
            </Field>
            <Field
              label="Target audience"
              hint="Who you want to reach — age, interests, location. Example: urban professionals 25-35 who care about sustainability"
            >
              <Input
                value={form.audience ?? ''}
                onChange={(e) => set('audience', e.target.value)}
                placeholder="e.g. urban professionals 25-35"
              />
            </Field>
            <Field
              label="Brand voice / tone"
              hint="Personality of the writing. Example: cozy, witty, a little cheeky"
            >
              <Input
                value={form.voice ?? ''}
                onChange={(e) => set('voice', e.target.value)}
                placeholder="e.g. cozy, witty, a little cheeky"
              />
            </Field>
          </div>

          {/* Platforms: chips (not wrapped in a <label> so toggles don't bubble) */}
          <div className="field">
            <span className="field__label">Platforms</span>
            <div className="row">
              {PLATFORMS.map((p) => {
                const on = (form.platforms ?? []).includes(p)
                return (
                  <Button
                    key={p}
                    size="sm"
                    variant={on ? 'primary' : 'ghost'}
                    onClick={() => togglePlatform(p)}
                    aria-pressed={on}
                  >
                    {p}
                  </Button>
                )
              })}
            </div>
            <span className="field__hint">
              Click to select where you'll post. Example: Instagram + LinkedIn
            </span>
          </div>

          <Field
            label="Goals"
            hint="Measurable outcomes with a timeframe. Example: grow Instagram followers by 20% and drive weekday foot traffic in 90 days"
          >
            <Textarea
              rows={3}
              value={form.goals ?? ''}
              onChange={(e) => set('goals', e.target.value)}
              placeholder="e.g. grow Instagram followers 20% and drive weekday foot traffic in 90 days"
            />
          </Field>

          <Field
            label="Additional notes"
            hint="Optional. Constraints, competitors, or offers to mention. Example: highlight our new oat-milk range; avoid mentioning prices"
          >
            <Textarea
              rows={2}
              value={form.notes ?? ''}
              onChange={(e) => set('notes', e.target.value)}
              placeholder="Constraints, competitors, must-mention offers…"
            />
          </Field>
        </>
      ) : (
        <Field
          label="Brief"
          hint="Write it as a paragraph covering name, product, audience, voice, platforms and goal. Example: Brand 'Bean There', a vegan coffee shop in Bandra Mumbai. We roast our own beans and bake vegan pastries. Voice is cozy, witty, cheeky. Grow Instagram + LinkedIn among urban professionals 25-35; goal: +20% followers and more weekday foot traffic in 90 days."
        >
          <Textarea
            rows={10}
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder="Brand: 'Bean There', a vegan coffee shop in Bandra…"
          />
        </Field>
      )}

      <Button
        variant="primary"
        disabled={!canRun}
        loading={wizard.isEnqueuing}
        onClick={run}
      >
        <IconPlay /> Run Account Manager
      </Button>
    </Card>
  )
}
