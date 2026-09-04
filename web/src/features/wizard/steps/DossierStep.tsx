import { useState } from 'react'

import { useToast } from '@/components/feedback/ToastProvider'
import { IconAlert, IconArrowLeft, IconCheck, IconRefresh } from '@/components/icons'
import { Badge, Banner, Button, Card, Empty, Field, Textarea } from '@/components/ui'
import type { BrandDossier } from '@/types/domain'

import type { Wizard } from '../useWizard'

export function DossierStep({ wizard }: { wizard: Wizard }) {
  const dossier = wizard.state.dossier
  const { toast } = useToast()
  const [json, setJson] = useState(() => JSON.stringify(dossier ?? {}, null, 2))
  const [editing, setEditing] = useState(false)

  if (!dossier) {
    return <Empty>Waiting for the Account Manager to produce a dossier…</Empty>
  }

  // Guardrail: the agent halts instead of guessing when the brief is too thin.
  if (dossier.insufficient_context) {
    return (
      <Card title="Needs more information">
        <Banner tone="warning">
          <span className="row" style={{ gap: 6 }}>
            <IconAlert size={15} />
            Missing: <strong>{(dossier.missing_fields ?? []).join(', ') || 'unknown'}</strong>
          </span>
        </Banner>
        <Button onClick={() => wizard.goToStage('brief')}>
          <IconArrowLeft /> Edit brief
        </Button>
      </Card>
    )
  }

  const approve = () => {
    let parsed: BrandDossier = dossier
    if (editing) {
      try {
        parsed = JSON.parse(json) as BrandDossier
      } catch {
        toast('Invalid JSON — fix it before approving.', 'error')
        return
      }
    }
    wizard.patchState({ dossier: parsed })
    wizard.enqueue(
      'strategy',
      { dossier: parsed, feedback: [] },
      'Strategist + Validator',
    )
  }

  return (
    <Card title="Review: brand dossier">
      <div className="grid-2">
        <Metric label="Client" value={dossier.client_name} />
        <Metric label="Industry" value={dossier.industry} />
        <Metric label="Platforms" value={(dossier.target_platforms ?? []).join(', ')} />
      </div>

      <div className="stack" style={{ marginTop: 14 }}>
        <Line label="Voice" value={dossier.brand_voice} />
        <Line label="Audience" value={dossier.target_audience} />
        <Line label="Goals" value={(dossier.goals ?? []).join('; ')} />
        {dossier.kpis?.length > 0 && <Line label="KPIs" value={dossier.kpis.join('; ')} />}
      </div>

      <details
        style={{ marginTop: 14 }}
        onToggle={(e) => setEditing((e.currentTarget as HTMLDetailsElement).open)}
      >
        <summary className="small muted" style={{ cursor: 'pointer' }}>
          Edit dossier JSON
        </summary>
        <div style={{ marginTop: 10 }}>
          <Field label="Dossier">
            <Textarea
              mono
              rows={14}
              value={json}
              onChange={(e) => setJson(e.target.value)}
            />
          </Field>
        </div>
      </details>

      <div className="row" style={{ marginTop: 12 }}>
        <Button variant="primary" loading={wizard.isEnqueuing} onClick={approve}>
          <IconCheck /> Approve → Strategist
        </Button>
        <Button
          onClick={() =>
            wizard.enqueue(
              'dossier',
              { brief: wizard.state.brief ?? '' },
              'Account Manager → dossier',
            )
          }
        >
          <IconRefresh /> Re-run Account Manager
        </Button>
        <Button variant="ghost" onClick={() => wizard.goToStage('brief')}>
          <IconArrowLeft /> Edit brief
        </Button>
      </div>
    </Card>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="field__label">{label}</div>
      <div style={{ fontSize: 17, fontWeight: 650 }}>{value || '—'}</div>
    </div>
  )
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <Badge tone="accent">{label}</Badge>{' '}
      <span>{value || '—'}</span>
    </div>
  )
}
