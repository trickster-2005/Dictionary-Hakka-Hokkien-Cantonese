import { useMemo, useState } from 'react'
import { SearchBox } from './components/SearchBox'
import { TermResult } from './components/TermResult'
import { ThemeToggle } from './components/ThemeToggle'
import { useFavorites } from './hooks/useFavorites'
import { useHakkaVariant } from './hooks/useHakkaVariant'
import { useDictionary } from './db/client'
import './App.css'

function App() {
  const { db, status } = useDictionary()
  const [query, setQuery] = useState('')
  const [searched, setSearched] = useState<string | null>(null)
  const { favorites, toggleFavorite, isFavorite } = useFavorites()
  const { variant, setVariant } = useHakkaVariant()
  const [showFavorites, setShowFavorites] = useState(false)

  const found = useMemo(() => {
    if (!db || !searched) return false
    return db.hasMatch(searched)
  }, [db, searched])

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>粵台客 查詞</h1>
        <ThemeToggle />
      </header>

      <SearchBox
        value={query}
        onChange={setQuery}
        onSubmit={() => {
          setShowFavorites(false)
          setSearched(query.trim())
        }}
      />

      <div className="favorites-toggle">
        <button type="button" onClick={() => setShowFavorites((v) => !v)}>
          {showFavorites ? '回到搜尋結果' : `⭐ 收藏清單 (${favorites.length})`}
        </button>
      </div>

      {status === 'loading' && <p className="status-msg">資料庫載入中…</p>}
      {status === 'error' && <p className="status-msg">資料庫載入失敗,請重新整理再試一次。</p>}

      {status === 'ready' && db && showFavorites && (
        <div className="favorites-list">
          {favorites.length === 0 && <p className="status-msg">還沒有收藏的詞彙。</p>}
          {favorites.map((term) => (
            <TermResult
              key={term}
              db={db}
              term={term}
              hakkaVariant={variant}
              onHakkaVariantChange={setVariant}
              favorited={isFavorite(term)}
              onToggleFavorite={() => toggleFavorite(term)}
            />
          ))}
        </div>
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
              favorited={isFavorite(searched)}
              onToggleFavorite={() => toggleFavorite(searched)}
            />
          )}
        </>
      )}
    </div>
  )
}

export default App
