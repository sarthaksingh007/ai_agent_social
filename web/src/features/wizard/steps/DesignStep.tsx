import { useState } from 'react'

import { IconArrowLeft, IconImage } from '@/components/icons'
import { Button, Card, Empty } from '@/components/ui'

import type { Wizard } from '../useWizard'

export function DesignStep({ wizard }: { wizard: Wizard }) {
  const drafts = wizard.state.drafts ?? []
  const [multi, setMulti] = useState(false)

  // What each format produces, so we can tell the user the real image count.
  const counts = { post: 0, carousel: 0, reel: 0 }
  for (const d of drafts) counts[d.content_format ?? 'post']++
  const allSinglePosts = counts.carousel === 0 && counts.reel === 0
  // carousel = 3 imgs, reel = 1 cover, post = 1 (or 3 with variants).
  const totalImages =
    counts.carousel * 3 + counts.reel * 1 + counts.post * (multi ? 3 : 1)

  const design = () => {
    wizard.enqueue(
      'design',
      { posts: drafts, variants: multi ? 3 : 1 },
      `Designer → ${totalImages} image${totalImages === 1 ? '' : 's'}`,
    )
    // The batch is now the worker's; clear it and reopen copy for the next one.
    wizard.patchState({ drafts: null, stage: 'copy' })
  }

  if (drafts.length === 0) {
    return (
      <Card title="Design posters">
        <Empty>No approved drafts — go back and approve some copy first.</Empty>
        <div style={{ marginTop: 12 }}>
          <Button variant="ghost" onClick={() => wizard.goToStage('copy')}>
            <IconArrowLeft /> Back to copy
          </Button>
        </div>
      </Card>
    )
  }

  const parts = [
    counts.post && `${counts.post} single post${counts.post === 1 ? '' : 's'}`,
    counts.carousel && `${counts.carousel} carousel${counts.carousel === 1 ? '' : 's'} (3 slides each)`,
    counts.reel && `${counts.reel} reel cover${counts.reel === 1 ? '' : 's'}`,
  ].filter(Boolean)

  return (
    <Card title="Design visuals">
      <p className="muted">
        {drafts.length} approved draft{drafts.length === 1 ? '' : 's'} — {parts.join(', ')}. The
        brand kit, headline and CTA are composed into each image.
      </p>

      {/* Variants only make sense for single posts; carousels/reels already
          produce their own images (3 slides / 1 cover). */}
      {allSinglePosts && (
        <label className="row" style={{ gap: 8, margin: '10px 0 16px' }}>
          <input type="checkbox" checked={multi} onChange={(e) => setMulti(e.target.checked)} />
          <span>Generate 3 variants per post (pick the best later — costs more)</span>
        </label>
      )}

      <div className="row">
        <Button variant="primary" loading={wizard.isEnqueuing} onClick={design}>
          <IconImage /> Design {totalImages} image{totalImages === 1 ? '' : 's'}
        </Button>
        <Button variant="ghost" onClick={() => wizard.goToStage('copy')}>
          <IconArrowLeft /> Back to copy
        </Button>
      </div>
    </Card>
  )
}
