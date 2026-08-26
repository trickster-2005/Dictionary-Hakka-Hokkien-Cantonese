import { LANG_ORDER } from '../constants'
import { LanguageCard } from './LanguageCard'
import { FavoriteStar } from './FavoriteStar'
import type { DictionaryClient } from '../db/client'
import type { HakkaVariant } from '../types'

interface Props {
  db: DictionaryClient
  term: string
  hakkaVariant: HakkaVariant
  onHakkaVariantChange: (value: HakkaVariant) => void
  favorited: boolean
  onToggleFavorite: () => void
}

export function TermResult({
  db,
  term,
  hakkaVariant,
  onHakkaVariantChange,
  favorited,
  onToggleFavorite,
}: Props) {
  return (
    <section className="term-block">
      <div className="term-header">
        <h2>{term}</h2>
        <FavoriteStar active={favorited} onToggle={onToggleFavorite} />
      </div>
      <div className="card-row">
        {LANG_ORDER.map((lang) => (
          <LanguageCard
            key={lang}
            lang={lang}
            entries={db.getEntriesForQuery(term, lang, hakkaVariant)}
            hakkaVariant={hakkaVariant}
            onHakkaVariantChange={onHakkaVariantChange}
          />
        ))}
      </div>
    </section>
  )
}
