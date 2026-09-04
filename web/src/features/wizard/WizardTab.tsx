import { IconRefresh } from '@/components/icons'
import { Button } from '@/components/ui'
import type { Project } from '@/types/domain'

import { Stepper } from './Stepper'
import { BriefStep } from './steps/BriefStep'
import { CopyStep } from './steps/CopyStep'
import { DesignStep } from './steps/DesignStep'
import { DossierStep } from './steps/DossierStep'
import { StrategyStep } from './steps/StrategyStep'
import { WeeklyStep } from './steps/WeeklyStep'
import { useWizard } from './useWizard'

export function WizardTab({ project }: { project: Project }) {
  const wizard = useWizard(project)

  return (
    <div className="stack">
      <div className="row row--between">
        <Stepper current={wizard.stage} />
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            if (window.confirm('Reset this campaign back to the brief?')) wizard.reset()
          }}
        >
          <IconRefresh /> Reset
        </Button>
      </div>

      {wizard.stage === 'brief' && <BriefStep wizard={wizard} />}
      {wizard.stage === 'dossier' && <DossierStep wizard={wizard} />}
      {wizard.stage === 'strategy' && <StrategyStep wizard={wizard} />}
      {wizard.stage === 'weekly' && <WeeklyStep wizard={wizard} />}
      {wizard.stage === 'copy' && <CopyStep wizard={wizard} />}
      {wizard.stage === 'design' && <DesignStep wizard={wizard} />}
    </div>
  )
}
