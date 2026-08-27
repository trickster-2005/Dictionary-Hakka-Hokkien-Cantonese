import { useCallback, useEffect, useMemo, useState } from 'react'
import { SearchBox } from './components/SearchBox'
import { SearchHistoryChips } from './components/SearchHistoryChips'
import { TermResult } from './components/TermResult'
import { LanguageCard } from './components/LanguageCard'
import { EntryModal } from './components/EntryModal'
import { ThemeToggle } from './components/ThemeToggle'
import { Footer } from './components/Footer'
import { useFavorites } from './hooks/useFavorites'
import { useHakkaVariant } from './hooks/useHakkaVariant'
import { useSearchHistory } from './hooks/useSearchHistory'
import { useDictionary, entryKey } from './db/client'
import { LANG_ORDER } from './constants'
import type { Entry, LangCode } from './types'
import './App.css'

function readQueryFromUrl(): string {
  return new URLSearchParams(window.location.search).get('q') ?? ''
}

function App() {
  const { db, status } = useDictionary()
  const [query, setQuery] = useState('')
  const [searched, setSearched] = useState<string | null>(null)
  const [modalEntry, setModalEntry] = useState<Entry | null>(null)
  const { favorites, toggleFavorite, isFavorite } = useFavorites()
  const { history, addSearch, clearHistory } = useSearchHistory()
  const { variant, setVariant } = useHakkaVariant()
  const [showFavorites, setShowFavorites] = useState(false)

  const runSearch = useCallback(
    (term: string, opts?: { skipUrlUpdate?: boolean }) => {
      const trimmed = term.trim()
      setShowFavorites(false)
      setQuery(trimmed)
      setSearched(trimmed)
      if (trimmed) addSearch(trimmed)
      if (!opts?.skipUrlUpdate) {
        const url = trimmed ? `?q=${encodeURIComponent(trimmed)}` : window.location.pathname
        window.history.pushState({ q: trimmed }, '', url)
      }
    },
    [addSearch],
  )

  // Load whatever ?q= is in the URL on first render (a shared link), and
  // keep the back/forward buttons working since search updates history too.
  useEffect(() => {
    const initial = readQueryFromUrl()
    if (initial) runSearch(initial, { skipUrlUpdate: true })
    const onPopState = () => runSearch(readQueryFromUrl(), { skipUrlUpdate: true })
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const found = useMemo(() => {
    if (!db || !searched) return false
    return db.hasMatch(searched)
  }, [db, searched])

  // favorites is already newest-first (toggleFavorite prepends), so grouping
  // by language in a single pass keeps each group newest-first too.
  const favoritesByLang = useMemo(() => {
    const grouped: Record<LangCode, Entry[]> = { yue: [], nan: [], hak: [] }
    if (!db) return grouped
    for (const key of favorites) {
      const entry = db.getEntryByKey(key)
      if (entry) grouped[entry.lang].push(entry)
    }
    return grouped
  }, [db, favorites])

  const isEntryFavorite = useCallback((entry: Entry) => isFavorite(entryKey(entry)), [isFavorite])
  const toggleEntryFavorite = useCallback(
    (entry: Entry) => toggleFavorite(entryKey(entry)),
    [toggleFavorite],
  )

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>粵台客 查詞</h1>
        <div className="app-header__controls">
          <button type="button" className="favorites-toggle" onClick={() => setShowFavorites((v) => !v)}>
            {showFavorites ? '回到搜尋結果' : `♥ 收藏清單 (${favorites.length})`}
          </button>
          <ThemeToggle />
        </div>
      </header>

      <SearchBox value={query} onChange={setQuery} onSubmit={() => runSearch(query)} />

      <SearchHistoryChips history={history} onSelect={runSearch} onClear={clearHistory} />

      {status === 'loading' && <p className="status-msg">資料庫載入中…</p>}
      {status === 'error' && <p className="status-msg">資料庫載入失敗,請重新整理再試一次。</p>}

      {status === 'ready' && db && showFavorites && (
        <section className="term-block">
          <div className="card-row">
            {LANG_ORDER.map((lang) => (
              <LanguageCard
                key={lang}
                lang={lang}
                entries={favoritesByLang[lang]}
                hakkaVariant={variant}
                onHakkaVariantChange={setVariant}
                isFavorite={isEntryFavorite}
                onToggleFavorite={toggleEntryFavorite}
                onOpenDetail={setModalEntry}
                emptyMessage="尚無收藏。"
              />
            ))}
          </div>
        </section>
      )}

      {status === 'ready' && db && !showFavorites && searched !== null && (
        <>
          {!found && <p className="status-msg">查無「{searched}」,換個詞試試看。</p>}
          {found && (
            <TermResult
              db={db}
              term={searched}
              hakkaVariant={variant}
              onHakkaVariantChange={setVariant}
              isFavorite={isEntryFavorite}
              onToggleFavorite={toggleEntryFavorite}
              onOpenDetail={setModalEntry}
            />
          )}
        </>
      )}

      <Footer />

      {modalEntry && (
        <EntryModal
          entry={modalEntry}
          favorited={isEntryFavorite(modalEntry)}
          onToggleFavorite={() => toggleEntryFavorite(modalEntry)}
          onClose={() => setModalEntry(null)}
        />
      )}
    </div>
  )
}

export default App
