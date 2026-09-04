import { IconCheck, IconChevronRight } from '@/components/icons'
import type { WizardStage } from '@/types/domain'

import { STAGE_LABELS, STAGES } from './useWizard'

export function Stepper({ current }: { current: WizardStage }) {
  const currentIndex = Math.max(0, STAGES.indexOf(current))

  return (
    <nav className="stepper" aria-label="Campaign progress">
      {STAGES.map((s, i) => {
        const done = i < currentIndex
        const active = i === currentIndex
        return (
          <span key={s} className="row" style={{ gap: 6 }}>
            <span
              className={`step ${done ? 'step--done' : ''} ${active ? 'step--current' : ''}`}
              aria-current={active ? 'step' : undefined}
            >
              {done && <IconCheck size={13} />}
              {STAGE_LABELS[s]}
            </span>
            {i < STAGES.length - 1 && <IconChevronRight size={13} className="step-arrow" />}
          </span>
        )
      })}
    </nav>
  )
}
