import type { MouseEvent } from 'react'
import { LANG_LABELS } from '../constants'
import { PlayButton } from './PlayButton'
import { FavoriteStar } from './FavoriteStar'
import type { Entry } from '../types'

interface Props {
  entry: Entry
  favorited: boolean
  onToggleFavorite: () => void
  /** Shown as a small label when this card appears outside its language
   * column (e.g. in the flat favorites list). */
  showLangLabel?: boolean
  /** Desktop only: clicking the card (but not a link/button inside it) opens
   * a bigger detail view instead of sending people to the external source. */
  onOpenDetail?: (entry: Entry) => void
}

const DESKTOP_QUERY = '(min-width: 861px)'

export function EntryCard({ entry, favorited, onToggleFavorite, showLangLabel, onOpenDetail }: Props) {
  const clickable = Boolean(onOpenDetail)

  function handleClick(e: MouseEvent<HTMLElement>) {
    if (!onOpenDetail) return
    if ((e.target as HTMLElement).closest('a, button, select')) return
    if (!window.matchMedia(DESKTOP_QUERY).matches) return
    onOpenDetail(entry)
  }

  return (
    <article
      className={`entry-card${clickable ? ' entry-card--clickable' : ''}`}
      onClick={handleClick}
    >
      <div className="entry-card__top">
        {showLangLabel && <span className="entry-card__lang-label">{LANG_LABELS[entry.lang]}</span>}
        <div className="entry-card__script">{entry.script}</div>
      </div>
      {(entry.pronunciation1 || entry.pronunciation2 || entry.audio.length > 0) && (
        <div className="entry-card__pronunciation">
          {entry.pronunciation1}
          {entry.pronunciation2 ? <span> · {entry.pronunciation2}</span> : null}
          {entry.audio.map((a) => (
            <PlayButton key={a.id} src={a.audioUrl} />
          ))}
        </div>
      )}
      {entry.registerTag && <span className="tag">{entry.registerTag}</span>}

      <div className={`entry-card__body${clickable ? ' entry-card__body--clamped' : ''}`}>
        {entry.definition && <p className="entry-card__definition">{entry.definition}</p>}

        {entry.examples.map((ex) => (
          <div key={ex.id} className="example-block">
            <p className="example-block__text">
              {ex.exampleText}
              {ex.audioUrl && <PlayButton src={ex.audioUrl} label="播放例句發音" />}
            </p>
            {ex.exampleTranslationZh && (
              <p className="example-block__translation">{ex.exampleTranslationZh}</p>
            )}
          </div>
        ))}
      </div>

      <div className="source-links">
        <a className="source-link" href={entry.sourceUrl} target="_blank" rel="noreferrer">
          閱讀更多:{entry.sourceName}
        </a>
        {entry.lang === 'nan' && (
          <a
            className="source-link"
            href={`https://itaigi.tw/k/${encodeURIComponent(entry.script)}`}
            target="_blank"
            rel="noreferrer"
          >
            iTaigi 愛台語
          </a>
        )}
      </div>

      <FavoriteStar active={favorited} onToggle={onToggleFavorite} />
    </article>
  )
}
