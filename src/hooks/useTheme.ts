import { useEffect, useState } from 'react'

const STORAGE_KEY = 'words-lookup:theme'
type Theme = 'light' | 'dark'

// Defaults to light regardless of system preference; only a manual toggle
// switches to dark (and that choice is remembered).
function readStoredTheme(): Theme {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => readStoredTheme())

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      // ignore
    }
  }, [theme])

  const toggle = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))

  return { isDark: theme === 'dark', toggle }
}
