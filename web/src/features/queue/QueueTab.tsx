import { useJobs } from '@/api/hooks'
import { IconAlert, IconCheck, IconClock, IconCircle, IconPlay } from '@/components/icons'
import { Badge, Card, Empty, Spinner, type Tone } from '@/components/ui'
import type { JobStatus } from '@/types/domain'

const STATUS: Record<JobStatus, { tone: Tone; Icon: typeof IconCheck }> = {
  queued: { tone: 'warning', Icon: IconClock },
  running: { tone: 'success', Icon: IconPlay },
  done: { tone: 'info', Icon: IconCheck },
  failed: { tone: 'danger', Icon: IconAlert },
}

export function QueueTab({ projectId }: { projectId: number }) {
  const { data: jobs, isPending } = useJobs(projectId)

  if (isPending) return <Spinner />
  if (!jobs || jobs.length === 0) return <Empty>No jobs yet for this project.</Empty>

  return (
    <Card title="Job queue">
      <p className="muted small">
        Every run adds a job here. The worker processes one at a time — extra work waits
        its turn and nothing blocks the UI.
      </p>

      <div className="stack">
        {jobs.map((j) => {
          const { tone, Icon } = STATUS[j.status] ?? { tone: 'neutral' as Tone, Icon: IconCircle }
          return (
            <div key={j.id} className="card" style={{ boxShadow: 'none' }}>
              <div className="row row--between">
                <span className="row" style={{ gap: 8 }}>
                  <Badge tone={tone}>
                    <Icon size={13} /> {j.status}
                  </Badge>
                  <strong>{j.label || j.job_type}</strong>
                </span>
                {j.agent && <span className="muted small">{j.agent}</span>}
              </div>
              {j.error && (
                <p className="small" style={{ color: 'var(--danger)', marginTop: 6 }}>
                  {j.error.slice(0, 300)}
                </p>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}
