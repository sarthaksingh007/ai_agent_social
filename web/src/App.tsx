import { useEffect, useState } from 'react'

import { useConfig, useProject, useProjects } from '@/api/hooks'
import { AgentPanel } from '@/components/layout/AgentPanel'
import { IconAlert, IconClipboard, IconList, IconPalette, IconRocket } from '@/components/icons'
import { Banner, Empty, Spinner } from '@/components/ui'
import { ApprovalTab } from '@/features/approval/ApprovalTab'
import { BrandKitTab } from '@/features/brandkit/BrandKitTab'
import { ProjectSidebar } from '@/features/projects/ProjectSidebar'
import { QueueTab } from '@/features/queue/QueueTab'
import { WizardTab } from '@/features/wizard/WizardTab'

const TABS = [
  { id: 'wizard', label: 'Campaign wizard', Icon: IconRocket },
  { id: 'approval', label: 'Approval desk', Icon: IconClipboard },
  { id: 'brand', label: 'Brand kit', Icon: IconPalette },
  { id: 'queue', label: 'Queue', Icon: IconList },
] as const

type TabId = (typeof TABS)[number]['id']

const ACTIVE_PROJECT_KEY = 'agency.activeProject'

export function App() {
  const { data: config } = useConfig()
  const { data: projects } = useProjects()
  const [tab, setTab] = useState<TabId>('wizard')

  const [projectId, setProjectId] = useState<number | null>(() => {
    const stored = localStorage.getItem(ACTIVE_PROJECT_KEY)
    return stored ? Number(stored) : null
  })

  // Keep the selection valid: fall back to the first project if the stored one
  // was deleted (possibly from another tab).
  useEffect(() => {
    if (!projects) return
    const exists = projectId !== null && projects.some((p) => p.id === projectId)
    if (!exists) setProjectId(projects[0]?.id ?? null)
  }, [projects, projectId])

  useEffect(() => {
    if (projectId === null) localStorage.removeItem(ACTIVE_PROJECT_KEY)
    else localStorage.setItem(ACTIVE_PROJECT_KEY, String(projectId))
  }, [projectId])

  const { data: project, isPending: projectPending } = useProject(projectId)

  return (
    <div className="app">
      <ProjectSidebar activeId={projectId} onSelect={setProjectId} />

      <main className="main">
        {config && config.problems.length > 0 && (
          <Banner tone="warning">
            <div className="row" style={{ gap: 6 }}>
              <IconAlert size={15} />
              <strong>Setup:</strong> {config.problems.join(' · ')}
            </div>
          </Banner>
        )}

        <AgentPanel />

        {projectId === null ? (
          <Empty>Create or select a project in the sidebar to begin.</Empty>
        ) : projectPending || !project ? (
          <Spinner />
        ) : (
          <>
            <div className="row row--between" style={{ marginBottom: 10 }}>
              <h2>{project.name}</h2>
              {config && (
                <span className="muted small">
                  {Object.entries(config.models)
                    .map(([role, model]) => `${role}: ${model.split('/').pop()}`)
                    .join(' · ')}
                </span>
              )}
            </div>

            <div className="tabs" role="tablist">
              {TABS.map(({ id, label, Icon }) => (
                <button
                  key={id}
                  role="tab"
                  className="tab"
                  aria-selected={tab === id}
                  onClick={() => setTab(id)}
                >
                  <span className="row" style={{ gap: 6 }}>
                    <Icon size={15} />
                    {label}
                  </span>
                </button>
              ))}
            </div>

            {tab === 'wizard' && <WizardTab project={project} />}
            {tab === 'approval' && <ApprovalTab projectId={project.id} />}
            {tab === 'brand' && <BrandKitTab project={project} />}
            {tab === 'queue' && <QueueTab projectId={project.id} />}
          </>
        )}
      </main>
    </div>
  )
}
