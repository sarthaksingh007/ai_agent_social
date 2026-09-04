/** Brand switcher. Each project carries its own wizard state, posts and kit. */
import { useState } from 'react'

import { useCreateProject, useDeleteProject, useProjects } from '@/api/hooks'
import { useToast } from '@/components/feedback/ToastProvider'
import { IconFolder, IconPlus, IconTrash } from '@/components/icons'
import { Button, Input, Spinner } from '@/components/ui'
import { ThemeToggle } from '@/theme/ThemeToggle'

interface Props {
  activeId: number | null
  onSelect: (id: number | null) => void
}

export function ProjectSidebar({ activeId, onSelect }: Props) {
  const { data: projects, isPending } = useProjects()
  const createProject = useCreateProject()
  const deleteProject = useDeleteProject()
  const { toast } = useToast()
  const [name, setName] = useState('')

  const handleCreate = () => {
    const trimmed = name.trim()
    if (!trimmed) return
    createProject.mutate(trimmed, {
      onSuccess: (project) => {
        setName('')
        onSelect(project.id)
        toast(`Created “${project.name}”`)
      },
      onError: (err) => toast(err.message, 'error'),
    })
  }

  const handleDelete = (id: number, projectName: string) => {
    if (!window.confirm(`Delete “${projectName}” and all of its posts?`)) return
    deleteProject.mutate(id, {
      onSuccess: () => {
        if (activeId === id) onSelect(null)
        toast(`Deleted “${projectName}”`)
      },
      onError: (err) => toast(err.message, 'error'),
    })
  }

  return (
    <aside className="sidebar">
      <div className="row row--between">
        <h3 className="row" style={{ gap: 7 }}>
          <IconFolder size={18} /> Projects
        </h3>
        <ThemeToggle />
      </div>

      {isPending ? (
        <Spinner />
      ) : projects && projects.length > 0 ? (
        <div className="project-list">
          {projects.map((p) => (
            <button
              key={p.id}
              className="project-item"
              aria-current={p.id === activeId}
              onClick={() => onSelect(p.id)}
            >
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.name}</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="muted small">No projects yet — create one below.</p>
      )}

      <div>
        <Input
          placeholder="e.g. Umami Spices"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          aria-label="New brand or project name"
        />
        <div style={{ height: 8 }} />
        <Button
          variant="primary"
          block
          disabled={!name.trim()}
          loading={createProject.isPending}
          onClick={handleCreate}
        >
          <IconPlus /> Create project
        </Button>
      </div>

      <div className="spacer" />

      {activeId !== null && (
        <Button
          variant="danger"
          block
          size="sm"
          loading={deleteProject.isPending}
          onClick={() => {
            const proj = projects?.find((p) => p.id === activeId)
            if (proj) handleDelete(proj.id, proj.name)
          }}
        >
          <IconTrash /> Delete this project
        </Button>
      )}
    </aside>
  )
}
