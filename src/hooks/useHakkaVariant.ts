import { useEffect, useState } from 'react'
import type { HakkaVariant } from '../types'

const STORAGE_KEY = 'words-lookup:hakka-variant'

function readVariant(): HakkaVariant {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw === 'sixian' ? 'sixian' : 'hailu'
  } catch {
    return 'hailu'
  }
}

export function useHakkaVariant() {
  const [variant, setVariant] = useState<HakkaVariant>(() => readVariant())

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, variant)
    } catch {
      // ignore
    }
  }, [variant])

  return { variant, setVariant }
}
