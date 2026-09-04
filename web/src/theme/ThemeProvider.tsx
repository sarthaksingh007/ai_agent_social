/**
 * Theme state: 'system' (default), 'light', or 'dark'.
 *
 * Only an explicit choice writes `data-theme` on <html>; 'system' clears it and
 * lets the `prefers-color-scheme` block in globals.css decide. The choice is
 * persisted so a reload doesn't flash back to the OS setting.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export type Theme = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'agency.theme'

interface ThemeContextValue {
  theme: Theme
  setTheme: (t: Theme) => void
  /** Cycles system → light → dark → system. */
  cycle: () => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function readStored(): Theme {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw === 'light' || raw === 'dark' || raw === 'system' ? raw : 'system'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStored)

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const setTheme = useCallback((t: Theme) => setThemeState(t), [])

  const cycle = useCallback(
    () =>
      setThemeState((prev) =>
        prev === 'system' ? 'light' : prev === 'light' ? 'dark' : 'system',
      ),
    [],
  )

  const value = useMemo(() => ({ theme, setTheme, cycle }), [theme, setTheme, cycle])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>')
  return ctx
}
