import { IconArrowLeft, IconCheck } from '@/components/icons'
import { Button, Card, DataTable, Empty } from '@/components/ui'
import type { PostStructure } from '@/types/domain'

import type { Wizard } from '../useWizard'

export function WeeklyStep({ wizard }: { wizard: Wizard }) {
  const weeks = wizard.state.weeks ?? []

  return (
    <div className="stack">
      {weeks.length === 0 ? (
        <Empty>No weekly plan yet — approve a strategy first.</Empty>
      ) : (
        weeks.map((w) => (
          <Card
            key={w.week_number}
            title={`Week ${w.week_number} — ${w.theme} (${w.posts.length} posts)`}
          >
            <DataTable<PostStructure & Record<string, unknown>>
              rows={w.posts as (PostStructure & Record<string, unknown>)[]}
              columns={['date', 'platform', 'pillar', 'angle_and_objective']}
            />
          </Card>
        ))
      )}

      <div className="row">
        <Button variant="primary" onClick={() => wizard.goToStage('copy')}>
          <IconCheck /> Approve → write copy
        </Button>
        <Button variant="ghost" onClick={() => wizard.goToStage('strategy')}>
          <IconArrowLeft /> Back to strategy
        </Button>
      </div>
    </div>
  )
}
