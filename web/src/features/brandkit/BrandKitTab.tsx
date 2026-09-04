import { useEffect, useState } from 'react'

import { useBrandKit, useSaveBrandKit } from '@/api/hooks'
import { useToast } from '@/components/feedback/ToastProvider'
import { IconSave } from '@/components/icons'
import { Button, Card, Field, Input, Textarea } from '@/components/ui'
import type { BrandKit, Project } from '@/types/domain'

const EMPTY: Omit<BrandKit, 'client_name'> = {
  colors: [],
  font_style: '',
  logo_description: '',
  handle: '',
  website: '',
  style_notes: '',
}

export function BrandKitTab({ project }: { project: Project }) {
  const { toast } = useToast()
  const saveKit = useSaveBrandKit()

  // Default to the dossier's client name, falling back to the project name.
  const [client, setClient] = useState(
    () => project.state?.dossier?.client_name || project.name,
  )
  const { data: existing } = useBrandKit(client)
  const [kit, setKit] = useState(EMPTY)

  useEffect(() => {
    setKit({ ...EMPTY, ...(existing ?? {}) })
  }, [existing])

  const set = <K extends keyof typeof kit>(key: K, value: (typeof kit)[K]) =>
    setKit((prev) => ({ ...prev, [key]: value }))

  const save = () =>
    saveKit.mutate(
      { client_name: client.trim(), ...kit },
      {
        onSuccess: () => toast(`Saved brand kit for ${client}`),
        onError: (e) => toast(e.message, 'error'),
      },
    )

  return (
    <Card title="Brand kit">
      <p className="muted small">
        Stored per client and auto-injected into every poster and caption.
      </p>

      <Field label="Client name">
        <Input value={client} onChange={(e) => setClient(e.target.value)} />
      </Field>

      <div className="grid-2">
        <Field label="Colors" hint="Comma-separated hex, e.g. #E63946, #1D3557">
          <Input
            value={kit.colors.join(', ')}
            onChange={(e) =>
              set(
                'colors',
                e.target.value
                  .split(',')
                  .map((c) => c.trim())
                  .filter(Boolean),
              )
            }
          />
        </Field>
        <Field label="Typography style">
          <Input
            value={kit.font_style}
            onChange={(e) => set('font_style', e.target.value)}
            placeholder="elegant modern serif"
          />
        </Field>
      </div>

      <Field label="Logo description" hint="Literal enough for the designer to render.">
        <Input
          value={kit.logo_description}
          onChange={(e) => set('logo_description', e.target.value)}
          placeholder="minimal golden mortar-and-pestle icon"
        />
      </Field>

      <div className="grid-2">
        <Field label="Handle">
          <Input
            value={kit.handle}
            onChange={(e) => set('handle', e.target.value)}
            placeholder="@umamispices"
          />
        </Field>
        <Field label="Website">
          <Input value={kit.website} onChange={(e) => set('website', e.target.value)} />
        </Field>
      </div>

      <Field label="Style notes" hint="Extra do's and don'ts for visuals and voice.">
        <Textarea
          rows={3}
          value={kit.style_notes}
          onChange={(e) => set('style_notes', e.target.value)}
        />
      </Field>

      <Button
        variant="primary"
        disabled={!client.trim()}
        loading={saveKit.isPending}
        onClick={save}
      >
        <IconSave /> Save brand kit
      </Button>
    </Card>
  )
}
