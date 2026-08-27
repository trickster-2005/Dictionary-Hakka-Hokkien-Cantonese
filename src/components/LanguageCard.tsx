import { LANG_LABELS } from '../constants'
import { HakkaVariantSelect } from './HakkaVariantSelect'
import { EntryCard } from './EntryCard'
import type { Entry, HakkaVariant, LangCode } from '../types'

interface Props {
  lang: LangCode
  entries: Entry[]
  hakkaVariant: HakkaVariant
  onHakkaVariantChange: (value: HakkaVariant) => void
  isFavorite: (entry: Entry) => boolean
  onToggleFavorite: (entry: Entry) => void
  onOpenDetail: (entry: Entry) => void
  emptyMessage?: string
}

export function LanguageCard({
  lang,
  entries,
  hakkaVariant,
  onHakkaVariantChange,
  isFavorite,
  onToggleFavorite,
  onOpenDetail,
  emptyMessage = '查無資料。',
}: Props) {
  return (
    <div className={`lang-column lang-column--${lang}`}>
      <div className="lang-column__header">
        <h3>{LANG_LABELS[lang]}</h3>
        {lang === 'hak' && (
          <HakkaVariantSelect value={hakkaVariant} onChange={onHakkaVariantChange} />
        )}
      </div>

      {entries.length === 0 && <p className="lang-card__placeholder">{emptyMessage}</p>}

      {entries.length > 0 && (
        <div className="lang-column__cards">
          {entries.map((entry) => (
            <EntryCard
              key={entry.id}
              entry={entry}
              favorited={isFavorite(entry)}
              onToggleFavorite={() => onToggleFavorite(entry)}
              onOpenDetail={onOpenDetail}
            />
          ))}
        </div>
      )}
    </div>
  )
}
