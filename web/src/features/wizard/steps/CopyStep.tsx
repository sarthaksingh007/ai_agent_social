import { useEffect, useState } from 'react'

import { IconArrowLeft, IconCheck, IconPen, IconRefresh } from '@/components/icons'
import { Badge, Button, Card, Field, Input, Textarea } from '@/components/ui'
import type { ContentFormat, Draft } from '@/types/domain'

import type { Wizard } from '../useWizard'

const FORMATS: { value: ContentFormat; label: string; hint: string }[] = [
  { value: 'post', label: 'Single post', hint: 'One image + caption.' },
  { value: 'carousel', label: 'Carousel (3)', hint: '3 swipeable slides, one image each.' },
  { value: 'reel', label: 'Reel', hint: 'Shot-by-shot video script + a cover image.' },
]

const FORMAT_LABEL: Record<ContentFormat, string> = {
  post: 'Single post',
  carousel: 'Carousel',
  reel: 'Reel',
}

export function CopyStep({ wizard }: { wizard: Wizard }) {
  const serverDrafts = wizard.state.drafts ?? null
  const calendar = wizard.state.strategy?.one_month_calendar_skeleton ?? []

  // Local buffer so typing doesn't round-trip to the server on every keystroke.
  const [drafts, setDrafts] = useState<Draft[] | null>(serverDrafts)

  // Re-sync when the worker delivers a fresh batch (identity check is enough:
  // the worker replaces the array wholesale).
  useEffect(() => setDrafts(serverDrafts), [serverDrafts])

  const [limit, setLimit] = useState(() => Math.min(3, Math.max(1, calendar.length)))
  const [format, setFormat] = useState<ContentFormat>(wizard.state.copyFormat ?? 'post')

  if (!drafts || drafts.length === 0) {
    const maxLimit = Math.max(1, Math.min(calendar.length, 8))
    const activeFormat = FORMATS.find((f) => f.value === format)
    return (
      <Card title="Write the copy">
        {/* Format picker: the person chooses what to create. */}
        <div className="field">
          <span className="field__label">Format</span>
          <div className="row">
            {FORMATS.map((f) => (
              <Button
                key={f.value}
                size="sm"
                variant={format === f.value ? 'primary' : 'ghost'}
                onClick={() => setFormat(f.value)}
                aria-pressed={format === f.value}
              >
                {f.label}
              </Button>
            ))}
          </div>
          <span className="field__hint">{activeFormat?.hint}</span>
        </div>

        <Field
          label={`How many ${FORMAT_LABEL[format].toLowerCase()}s to write: ${limit}`}
          hint={`${calendar.length} slots available in the calendar.`}
        >
          <input
            type="range"
            min={1}
            max={maxLimit}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            style={{ width: '100%' }}
          />
        </Field>
        <div className="row">
          <Button
            variant="primary"
            disabled={calendar.length === 0}
            loading={wizard.isEnqueuing}
            onClick={() => {
              wizard.patchState({ copyFormat: format })
              wizard.enqueue(
                'copy',
                { dossier: wizard.state.dossier, posts: calendar, limit, content_format: format },
                `Copywriter → ${limit} ${FORMAT_LABEL[format].toLowerCase()}(s)`,
              )
            }}
          >
            <IconPen /> Run Copywriter
          </Button>
          <Button variant="ghost" onClick={() => wizard.goToStage('weekly')}>
            <IconArrowLeft /> Back to weekly
          </Button>
        </div>
      </Card>
    )
  }

  const update = (index: number, patch: Partial<Draft>) =>
    setDrafts((prev) =>
      prev ? prev.map((d, i) => (i === index ? { ...d, ...patch } : d)) : prev,
    )

  return (
    <div className="stack">
      <p className="muted small">
        Edit the copy before any image is generated — designing is the expensive step.
      </p>

      {drafts.map((d, i) => (
        <Card
          key={d.post_id ?? i}
          title={
            <span className="row" style={{ gap: 8 }}>
              <span>{`Post ${i + 1} · ${d.pillar}`}</span>
              <Badge tone="accent">{FORMAT_LABEL[d.content_format ?? 'post']}</Badge>
            </span>
          }
        >
          <div className="muted small" style={{ marginBottom: 10 }}>
            {(d.target_platforms ?? []).join(', ')} · {d.scheduled_date}
          </div>

          <Field label="Hook">
            <Input value={d.hook_text} onChange={(e) => update(i, { hook_text: e.target.value })} />
          </Field>

          <Field label="Caption">
            <Textarea
              rows={5}
              value={d.body_caption}
              onChange={(e) => update(i, { body_caption: e.target.value })}
            />
          </Field>

          <div className="grid-2">
            <Field label="CTA">
              <Input
                value={d.cta_text ?? ''}
                onChange={(e) => update(i, { cta_text: e.target.value })}
              />
            </Field>
            <Field label="Hashtags" hint="Space separated.">
              <Input
                value={(d.hashtags ?? []).join(' ')}
                onChange={(e) =>
                  update(i, { hashtags: e.target.value.split(/\s+/).filter(Boolean) })
                }
              />
            </Field>
          </div>

          {/* Carousel: show the 3 slides that will each become an image. */}
          {d.content_format === 'carousel' && (d.carousel_slides ?? []).length > 0 && (
            <div className="field">
              <span className="field__label">Carousel slides</span>
              <div className="stack" style={{ gap: 10 }}>
                {d.carousel_slides.map((s) => (
                  <div key={s.slide_no} className="card" style={{ padding: 12 }}>
                    <div className="row" style={{ gap: 8, marginBottom: 6 }}>
                      <Badge>Slide {s.slide_no}</Badge>
                      <strong>{s.headline}</strong>
                    </div>
                    {s.caption && <div className="muted small">{s.caption}</div>}
                    <div className="muted small" style={{ marginTop: 6, fontStyle: 'italic' }}>
                      🖼 {s.visual_generation_prompt}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Reel: show the script that the human can review before design. */}
          {d.content_format === 'reel' && d.reel_script && (
            <div className="field">
              <span className="field__label">
                Reel script · ~{d.reel_script.duration_seconds}s
              </span>
              <div className="card" style={{ padding: 12 }}>
                <div style={{ marginBottom: 8 }}>
                  <Badge tone="accent">Hook</Badge> {d.reel_script.hook}
                </div>
                <ol style={{ margin: '0 0 8px 18px', padding: 0 }}>
                  {d.reel_script.scenes.map((sc, si) => (
                    <li key={si} style={{ marginBottom: 6 }}>
                      <div>{sc.shot}</div>
                      {sc.on_screen_text && (
                        <div className="muted small">On-screen: “{sc.on_screen_text}”</div>
                      )}
                      {sc.voiceover && (
                        <div className="muted small">VO: “{sc.voiceover}”</div>
                      )}
                    </li>
                  ))}
                </ol>
                {d.reel_script.cta && (
                  <div>
                    <Badge tone="success">CTA</Badge> {d.reel_script.cta}
                  </div>
                )}
                {d.reel_script.audio_suggestion && (
                  <div className="muted small" style={{ marginTop: 6 }}>
                    🎵 {d.reel_script.audio_suggestion}
                  </div>
                )}
              </div>
            </div>
          )}

          <Field
            label={d.content_format === 'reel' ? 'Cover image brief' : 'Image brief'}
            hint="Literal scene description — no text, no metaphors."
          >
            <Textarea
              rows={3}
              value={d.visual_generation_prompt}
              onChange={(e) => update(i, { visual_generation_prompt: e.target.value })}
            />
          </Field>
        </Card>
      ))}

      <div className="row">
        <Button
          variant="primary"
          loading={wizard.isSaving}
          onClick={() => wizard.patchState({ drafts, stage: 'design' })}
        >
          <IconCheck /> Approve copy → design
        </Button>
        <Button onClick={() => wizard.patchState({ drafts: null })}>
          <IconRefresh /> Discard &amp; re-run Copywriter
        </Button>
        <Button variant="ghost" onClick={() => wizard.goToStage('weekly')}>
          <IconArrowLeft /> Back to weekly
        </Button>
      </div>
    </div>
  )
}
