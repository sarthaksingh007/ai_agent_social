/**
 * Live status strip. Highlights whichever agent the worker container is
 * executing right now and shows how much work is still lined up behind it.
 */
import type { ComponentType } from 'react'

import { useConfig, useWorkerStatus } from '@/api/hooks'
import {
  IconBriefcase,
  IconClipboard,
  IconClock,
  IconImage,
  IconPen,
  IconShield,
  IconTarget,
  type IconProps,
} from '@/components/icons'
import { Badge } from '@/components/ui'
import type { AgentName } from '@/types/domain'

const AGENT_ICON: Record<AgentName, ComponentType<IconProps>> = {
  'Account Manager': IconBriefcase,
  Strategist: IconTarget,
  Validator: IconShield,
  'Project Manager': IconClipboard,
  Copywriter: IconPen,
  Designer: IconImage,
}

export function AgentPanel() {
  const { data: config } = useConfig()
  const { data: status } = useWorkerStatus()

  const agents = config?.agents ?? []
  const active = status?.active_agent ?? null
  const running = status?.running ?? null
  const depth = status?.queue_depth ?? 0

  return (
    <section className="agent-panel" aria-label="Agent status">
      <div className="row row--between">
        <strong>Agents</strong>
        <div className="row">
          {running && (
            <Badge tone="success">
              {running.project_name}: {running.label || running.job_type}
            </Badge>
          )}
          {depth > 0 && (
            <Badge tone="warning">
              <IconClock size={13} /> {depth} queued
            </Badge>
          )}
          {!running && depth === 0 && <Badge>Idle</Badge>}
        </div>
      </div>

      <div className="agent-chips">
        {agents.map((a) => {
          const Icon = AGENT_ICON[a]
          const isActive = a === active
          return (
            <span key={a} className={`agent-chip ${isActive ? 'agent-chip--active' : ''}`}>
              {Icon && <Icon size={14} />}
              {a}
              {isActive && ' · working…'}
            </span>
          )
        })}
      </div>
    </section>
  )
}
