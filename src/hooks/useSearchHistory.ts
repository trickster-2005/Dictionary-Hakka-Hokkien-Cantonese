import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'words-lookup:history'
const MAX_HISTORY = 15

function readHistory(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === 'string') : []
  } catch {
    return []
  }
}

export function useSearchHistory() {
  const [history, setHistory] = useState<string[]>(() => readHistory())

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
    } catch {
      // ignore
    }
  }, [history])

  const addSearch = useCallback((term: string) => {
    if (!term) return
    setHistory((prev) => [term, ...prev.filter((t) => t !== term)].slice(0, MAX_HISTORY))
  }, [])

  const clearHistory = useCallback(() => setHistory([]), [])

  return { history, addSearch, clearHistory }
}
