import { IconMonitor, IconMoon, IconSun } from '@/components/icons'
import { Button } from '@/components/ui'

import { useTheme } from './ThemeProvider'

const FACE = {
  system: { Icon: IconMonitor, label: 'System' },
  light: { Icon: IconSun, label: 'Light' },
  dark: { Icon: IconMoon, label: 'Dark' },
} as const

export function ThemeToggle() {
  const { theme, cycle } = useTheme()
  const { Icon, label } = FACE[theme]
  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={cycle}
      title={`${label} theme — click to change`}
      aria-label={`Theme: ${label}. Click to change.`}
    >
      <Icon />
      <span className="small">{label}</span>
    </Button>
  )
}
