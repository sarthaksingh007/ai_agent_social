import { useState } from 'react'

import { IconArrowLeft, IconCheck, IconRefresh, IconX } from '@/components/icons'
import {
  Badge,
  Banner,
  Button,
  Card,
  DataTable,
  Empty,
  Field,
  Textarea,
} from '@/components/ui'
import type { PostStructure } from '@/types/domain'

import type { Wizard } from '../useWizard'

export function StrategyStep({ wizard }: { wizard: Wizard }) {
  const { strategy, validation, dossier } = wizard.state
  const [feedback, setFeedback] = useState('')

  const rerun = () => {
    const notes = [feedback.trim()].filter(Boolean)
    // A rejected strategy carries its own fix-list; fold it into the re-run.
    if (validation && !validation.approved) notes.push(...validation.correction_notes)
    wizard.enqueue(
      'strategy',
      { dossier, feedback: notes },
      'Strategist + Validator (revised)',
    )
  }

  return (
    <div className="stack">
      <Card title="Content pillars">
        {strategy ? (
          <div className="stack">
            {strategy.content_pillars.map((p) => (
              <div key={p.pillar_name} className="card" style={{ boxShadow: 'none' }}>
                <strong>{p.pillar_name}</strong>
                <div className="muted small">{p.justification}</div>
              </div>
            ))}
          </div>
        ) : (
          <Empty>The Strategist produced no strategy — re-run it below.</Empty>
        )}
      </Card>

      {strategy && strategy.one_month_calendar_skeleton.length > 0 && (
        <Card title="One-month calendar">
          <DataTable<PostStructure & Record<string, unknown>>
            rows={strategy.one_month_calendar_skeleton as (PostStructure &
              Record<string, unknown>)[]}
            columns={['date', 'platform', 'pillar', 'angle_and_objective']}
          />
        </Card>
      )}

      {validation && (
        <Card title="Adversarial validation">
          <Banner tone={validation.approved ? 'success' : 'danger'}>
            Validator: {validation.approved ? 'APPROVED' : 'REJECTED'}
          </Banner>
          <div className="stack">
            {validation.checks.map((c) => (
              <div key={c.dimension} className="row" style={{ gap: 8 }}>
                {c.passed ? (
                  <IconCheck size={15} style={{ color: 'var(--success)' }} />
                ) : (
                  <IconX size={15} style={{ color: 'var(--danger)' }} />
                )}
                <strong>{c.dimension}</strong>
                {!c.hard && <Badge>advisory</Badge>}
                <span className="muted small">{c.reason}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <Field label="Feedback for a re-run" hint="Optional — folded into the Strategist's next attempt.">
          <Textarea
            rows={3}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="e.g. lean harder into sustainability, fewer product posts"
          />
        </Field>
        <div className="row">
          <Button
            variant="primary"
            disabled={!strategy}
            loading={wizard.isEnqueuing}
            onClick={() =>
              wizard.enqueue('weekly', { strategy }, 'Project Manager → weekly plan')
            }
          >
            <IconCheck /> Approve → Project Manager
          </Button>
          <Button onClick={rerun}>
            <IconRefresh /> Re-run Strategist
          </Button>
          <Button variant="ghost" onClick={() => wizard.goToStage('dossier')}>
            <IconArrowLeft /> Back to dossier
          </Button>
        </div>
      </Card>
    </div>
  )
}
