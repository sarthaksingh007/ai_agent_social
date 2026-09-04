import { usePosts } from '@/api/hooks'
import { Card, Empty, Spinner } from '@/components/ui'

import { PostCard } from './PostCard'

export function ApprovalTab({ projectId }: { projectId: number }) {
  const { data: posts, isPending } = usePosts(projectId)

  if (isPending) return <Spinner />
  if (!posts || posts.length === 0) {
    return <Empty>No posts yet — finish the wizard to fill this queue.</Empty>
  }

  const pending = posts.filter((p) => p.status === 'Pending Human Review').length
  const approved = posts.filter((p) => p.status === 'Approved').length
  const published = posts.filter((p) => p.status === 'Published').length

  return (
    <div className="stack">
      <Card>
        <div className="grid-2">
          <Stat label="Pending" value={pending} />
          <Stat label="Approved" value={approved} />
          <Stat label="Published" value={published} />
          <Stat label="Total" value={posts.length} />
        </div>
      </Card>

      {posts.map((p) => (
        <PostCard key={p.post_id} post={p} projectId={projectId} />
      ))}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="field__label">{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700 }}>{value}</div>
    </div>
  )
}
