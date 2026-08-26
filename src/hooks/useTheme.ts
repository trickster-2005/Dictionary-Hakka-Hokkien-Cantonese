import { useEffect, useState } from 'react'

const STORAGE_KEY = 'words-lookup:theme'
type Theme = 'light' | 'dark'

function readStoredTheme(): Theme | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw === 'light' || raw === 'dark' ? raw : null
  } catch {
    return null
  }
}

export function useTheme() {
  const [override, setOverride] = useState<Theme | null>(() => readStoredTheme())

  useEffect(() => {
    const root = document.documentElement
    if (override) {
      root.setAttribute('data-theme', override)
    } else {
      root.removeAttribute('data-theme')
    }
    try {
      if (override) {
        localStorage.setItem(STORAGE_KEY, override)
      } else {
        localStorage.removeItem(STORAGE_KEY)
      }
    } catch {
      // ignore
    }
  }, [override])

  const toggle = () => {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    const current = override ?? (prefersDark ? 'dark' : 'light')
    setOverride(current === 'dark' ? 'light' : 'dark')
  }

  const isDark = override === 'dark' || (override === null && window.matchMedia('(prefers-color-scheme: dark)').matches)

  return { override, isDark, toggle }
}
