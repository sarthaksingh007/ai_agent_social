import { useEffect, useState } from 'react'

import { useEnqueueJob, usePatchPost, usePublishPost } from '@/api/hooks'
import { useToast } from '@/components/feedback/ToastProvider'
import {
  IconAlert,
  IconCheck,
  IconImage,
  IconRefresh,
  IconSave,
  IconSend,
  IconX,
} from '@/components/icons'
import { Badge, Button, Card, Field, Input, Textarea, type Tone } from '@/components/ui'
import type { Post, PostStatus } from '@/types/domain'

const STATUS_TONE: Record<PostStatus, Tone> = {
  'Pending Human Review': 'warning',
  Approved: 'success',
  Rejected: 'danger',
  Published: 'info',
}

export function PostCard({ post, projectId }: { post: Post; projectId: number }) {
  const patchPost = usePatchPost(projectId)
  const publishPost = usePublishPost(projectId)
  const enqueue = useEnqueueJob(projectId)
  const { toast } = useToast()

  const [hook, setHook] = useState(post.hook_text ?? '')
  const [caption, setCaption] = useState(post.body_caption ?? '')

  // Adopt server values when a regen rewrites this post underneath us.
  useEffect(() => {
    setHook(post.hook_text ?? '')
    setCaption(post.body_caption ?? '')
  }, [post.hook_text, post.body_caption])

  const setStatus = (status: PostStatus) =>
    patchPost.mutate(
      { postId: post.post_id, patch: { status } },
      { onSuccess: () => toast(`${post.post_id} → ${status}`) },
    )

  const save = () =>
    patchPost.mutate(
      { postId: post.post_id, patch: { hook_text: hook, body_caption: caption } },
      { onSuccess: () => toast('Copy saved') },
    )

  const regenerate = () => {
    // Persist edits first so the Designer regenerates against current copy.
    patchPost.mutate({
      postId: post.post_id,
      patch: { hook_text: hook, body_caption: caption },
    })
    enqueue.mutate(
      {
        job_type: 'regen',
        payload: {
          posts: [
            {
              post_id: post.post_id,
              client_name: post.client_name,
              scheduled_date: post.scheduled_date ?? '',
              target_platforms: post.target_platforms ?? [],
              pillar: post.pillar ?? '',
              hook_text: hook,
              body_caption: caption,
              hashtags: post.hashtags ?? [],
              cta_text: post.cta_text ?? '',
              visual_generation_prompt: post.visual_prompt ?? '',
              status: post.status,
            },
          ],
        },
        label: `Designer → regen ${post.post_id}`,
      },
      { onSuccess: () => toast('Queued for regeneration') },
    )
  }

  const publish = () =>
    publishPost.mutate(post.post_id, {
      onSuccess: (r) => toast(`Published via ${r.sent_via}`),
      onError: (e) => toast(e.message, 'error'),
    })

  const variants = post.image_variant_urls ?? []

  return (
    <Card>
      <div className="row row--between" style={{ marginBottom: 12 }}>
        <div>
          <strong>{post.client_name}</strong>
          <span className="muted small">
            {post.pillar ? ` · ${post.pillar}` : ''}
            {post.scheduled_date ? ` · ${post.scheduled_date}` : ''}
          </span>
        </div>
        <Badge tone={STATUS_TONE[post.status] ?? 'neutral'}>{post.status}</Badge>
      </div>

      <div className="post-grid">
        <div>
          <Field label="Hook">
            <Input value={hook} onChange={(e) => setHook(e.target.value)} />
          </Field>
          <Field label="Caption">
            <Textarea rows={6} value={caption} onChange={(e) => setCaption(e.target.value)} />
          </Field>
          {post.hashtags && post.hashtags.length > 0 && (
            <p className="muted small">{post.hashtags.join(' ')}</p>
          )}
          {post.platform_variants && post.platform_variants.length > 0 && (
            <details>
              <summary className="small muted" style={{ cursor: 'pointer' }}>
                Platform versions ({post.platform_variants.length})
              </summary>
              <div className="stack" style={{ marginTop: 8 }}>
                {post.platform_variants.map((v) => (
                  <div key={v.platform}>
                    <Badge tone="accent">{v.platform}</Badge>
                    <p className="small" style={{ whiteSpace: 'pre-wrap', marginTop: 4 }}>
                      {v.body_caption}
                    </p>
                    {v.hashtags?.length > 0 && (
                      <p className="muted small">{v.hashtags.join(' ')}</p>
                    )}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>

        <div>
          {variants.length > 1 ? (
            <>
              <div className="field__label">Pick a variant</div>
              <div className="variant-grid">
                {variants.map((v) => {
                  const chosen = v.path === post.image_path
                  return (
                    <button
                      key={v.path}
                      className="btn btn--ghost"
                      style={{ padding: 0, display: 'block' }}
                      onClick={() =>
                        patchPost.mutate({
                          postId: post.post_id,
                          patch: { image_path: v.path },
                        })
                      }
                      disabled={chosen}
                      title={chosen ? 'Selected' : 'Use this variant'}
                    >
                      <img
                        src={v.url}
                        alt=""
                        className={`poster ${chosen ? 'variant--chosen' : ''}`}
                        loading="lazy"
                      />
                    </button>
                  )
                })}
              </div>
            </>
          ) : post.image_url ? (
            <img src={post.image_url} alt="" className="poster" loading="lazy" />
          ) : post.image_path ? (
            <div className="banner banner--warning row" style={{ gap: 6 }}>
              <IconAlert size={15} /> Image file missing — regenerate.
            </div>
          ) : (
            <div className="empty">
              <IconImage size={22} />
              <div>No poster yet</div>
            </div>
          )}
        </div>
      </div>

      <div className="row" style={{ marginTop: 14 }}>
        <Button size="sm" loading={patchPost.isPending} onClick={save}>
          <IconSave /> Save
        </Button>
        <Button size="sm" variant="primary" onClick={() => setStatus('Approved')}>
          <IconCheck /> Approve
        </Button>
        <Button size="sm" variant="danger" onClick={() => setStatus('Rejected')}>
          <IconX /> Reject
        </Button>
        <Button size="sm" onClick={regenerate} loading={enqueue.isPending}>
          <IconRefresh /> Regenerate
        </Button>
        {post.status === 'Approved' && (
          <Button size="sm" variant="primary" loading={publishPost.isPending} onClick={publish}>
            <IconSend /> Publish
          </Button>
        )}
      </div>
    </Card>
  )
}
