import { LANG_LABELS } from '../constants'
import { HakkaVariantSelect } from './HakkaVariantSelect'
import { PlayButton } from './PlayButton'
import type { Entry, HakkaVariant, LangCode } from '../types'

interface Props {
  lang: LangCode
  entries: Entry[]
  hakkaVariant: HakkaVariant
  onHakkaVariantChange: (value: HakkaVariant) => void
}

export function LanguageCard({ lang, entries, hakkaVariant, onHakkaVariantChange }: Props) {
  return (
    <div className={`lang-column lang-column--${lang}`}>
      <div className="lang-column__header">
        <h3>{LANG_LABELS[lang]}</h3>
        {lang === 'hak' && (
          <HakkaVariantSelect value={hakkaVariant} onChange={onHakkaVariantChange} />
        )}
      </div>

      {entries.length === 0 && <p className="lang-card__placeholder">查無資料。</p>}

      {entries.map((entry) => (
        <article key={entry.id} className="entry-card">
          <div className="entry-card__script">{entry.script}</div>
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

          <div className="source-links">
            <a className="source-link" href={entry.sourceUrl} target="_blank" rel="noreferrer">
              閱讀更多:{entry.sourceName}
            </a>
            {lang === 'nan' && (
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
        </article>
      ))}
    </div>
  )
}
