import { LANG_ORDER } from '../constants'
import { LanguageCard } from './LanguageCard'
import type { DictionaryClient } from '../db/client'
import type { Entry, HakkaVariant } from '../types'

interface Props {
  db: DictionaryClient
  term: string
  hakkaVariant: HakkaVariant
  onHakkaVariantChange: (value: HakkaVariant) => void
  isFavorite: (entry: Entry) => boolean
  onToggleFavorite: (entry: Entry) => void
  onOpenDetail: (entry: Entry) => void
}

export function TermResult({
  db,
  term,
  hakkaVariant,
  onHakkaVariantChange,
  isFavorite,
  onToggleFavorite,
  onOpenDetail,
}: Props) {
  return (
    <section className="term-block">
      <div className="term-header">
        <h2>{term}</h2>
      </div>
      <div className="card-row">
        {LANG_ORDER.map((lang) => (
          <LanguageCard
            key={lang}
            lang={lang}
            entries={db.getEntriesForQuery(term, lang, hakkaVariant)}
            hakkaVariant={hakkaVariant}
            onHakkaVariantChange={onHakkaVariantChange}
            isFavorite={isFavorite}
            onToggleFavorite={onToggleFavorite}
            onOpenDetail={onOpenDetail}
          />
        ))}
      </div>
    </section>
  )
}
