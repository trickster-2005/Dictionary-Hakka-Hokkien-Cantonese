import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'words-lookup:favorites'

function readFavorites(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    // drop anything saved under an older key format (plain search term, or
    // numeric zh_term_id) — a valid key is always lang|variant|script|pron
    return parsed.filter((v): v is string => typeof v === 'string' && v.split('|').length === 4)
  } catch {
    return []
  }
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<string[]>(() => readFavorites())

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites))
    } catch {
      // localStorage unavailable (private mode / quota) — favorites just won't persist
    }
  }, [favorites])

  // Newest first — toggled cards are added at the front, not appended, so
  // the favorites view can show most-recently-saved first with no extra
  // timestamp bookkeeping.
  const toggleFavorite = useCallback((key: string) => {
    setFavorites((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [key, ...prev],
    )
  }, [])

  const isFavorite = useCallback((key: string) => favorites.includes(key), [favorites])

  return { favorites, toggleFavorite, isFavorite }
}
