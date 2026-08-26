import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'words-lookup:favorites'

function readFavorites(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    // ignore favorites saved by an older numeric-id format
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === 'string') : []
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

  const toggleFavorite = useCallback((term: string) => {
    setFavorites((prev) =>
      prev.includes(term) ? prev.filter((t) => t !== term) : [...prev, term],
    )
  }, [])

  const isFavorite = useCallback((term: string) => favorites.includes(term), [favorites])

  return { favorites, toggleFavorite, isFavorite }
}
