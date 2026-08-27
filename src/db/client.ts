import initSqlJs, { type Database, type SqlJsStatic } from 'sql.js'
import { useEffect, useState } from 'react'
import type { Entry, Example, HakkaVariant, LangCode, WordAudio } from '../types'

// A small, deliberately short list of extremely common variant-character
// pairs in this domain (not a general 異體字 dictionary). Applied only to
// the query side at search time — stored text is never rewritten — so a
// search for either spelling finds entries recorded under the other one.
const VARIANT_PAIRS: Array<[string, string]> = [
  ['菸', '煙'], // 抽菸 / 抽煙
  ['臺', '台'], // 臺灣 / 台灣
]

function registerWeight(tag: string | null): number {
  if (!tag) return 1
  if (tag.includes('書面語')) return 2
  if (tag.includes('口語')) return 0
  return 1
}

/** 台語: rank by which field matched — 詞目(headword) > 近義詞(synonym field)
 * > 解釋(gloss extracted from the definition). 客語: 詞目 > 對應華語(tagged
 * 'synonym' in parse_hak.py) > 相似詞(tagged 'gloss'). 粵語 is deliberately
 * left on the simpler direct-vs-alias distinction. */
function computeMatchRank(lang: LangCode, mHeadword: boolean, mSynonym: boolean, mGloss: boolean): number {
  if (mHeadword) return 0
  if (lang === 'nan' || lang === 'hak') {
    if (mSynonym) return 1
    if (mGloss) return 2
    return 3
  }
  return 1 // yue: any alias match, regardless of kind
}

function expandQueryVariants(query: string): string[] {
  let variants = new Set([query])
  for (const [a, b] of VARIANT_PAIRS) {
    const next = new Set(variants)
    for (const v of variants) {
      if (v.includes(a)) next.add(v.split(a).join(b))
      if (v.includes(b)) next.add(v.split(b).join(a))
    }
    variants = next
  }
  return Array.from(variants)
}

/** Stable-enough identity for favoriting one specific card (not the whole
 * searched term) — survives a dictionary.sqlite rebuild as long as the
 * entry's own script/pronunciation don't change, unlike the internal
 * auto-increment `id` which reshuffles on every rebuild. */
export function entryKey(entry: Entry): string {
  return [entry.lang, entry.variant ?? '', entry.script, entry.pronunciation1 ?? ''].join('|')
}

function rowToEntry(row: Record<string, string | number | null>, examples: Example[], audio: WordAudio[]): Entry {
  return {
    id: row.id as number,
    zhTermId: row.zh_term_id as number,
    lang: row.lang as LangCode,
    variant: (row.variant as HakkaVariant | null) ?? null,
    script: row.script as string,
    pronunciation1: row.pronunciation_1 as string | null,
    pronunciation2: row.pronunciation_2 as string | null,
    definition: row.definition as string | null,
    registerTag: row.register_tag as string | null,
    sourceName: row.source_name as string,
    sourceUrl: row.source_url as string,
    licenseNote: row.license_note as string,
    examples,
    audio,
  }
}

export class DictionaryClient {
  private db: Database

  constructor(db: Database) {
    this.db = db
  }

  hasMatch(query: string): boolean {
    const variants = expandQueryVariants(query)
    const placeholders = variants.map(() => '?').join(',')
    const stmt = this.db.prepare(
      `SELECT 1 FROM zh_terms WHERE headword IN (${placeholders})
       UNION
       SELECT 1 FROM aliases WHERE alias IN (${placeholders})
       LIMIT 1`,
    )
    stmt.bind([...variants, ...variants])
    const found = stmt.step()
    stmt.free()
    return found
  }

  /** All entries — across every distinct native headword — that this query
   * matches for one language (direct headword match, or via an alias pulled
   * from another entry's own Mandarin gloss). Multiple entries for the same
   * language are expected and are rendered as separate cards.
   *
   * Ranked so the most relevant cards come first: an entry whose OWN
   * headword literally is the searched term outranks one that only turned
   * up through an alias (e.g. searching 食 turning up every entry that
   * merely mentions "吃" somewhere) — this is the primary signal for every
   * language, including 台語/客語 which have no register_tag at all. Within
   * the same match tier, colloquial-tagged entries sort before
   * formal/written ones (currently only 粵語 carries that tag). */
  getEntriesForQuery(query: string, lang: LangCode, hakkaVariant: HakkaVariant): Entry[] {
    const variants = expandQueryVariants(query)
    const placeholders = variants.map(() => '?').join(',')
    const stmt = this.db.prepare(
      `SELECT DISTINCT e.*,
         CASE WHEN e.zh_term_id IN (SELECT id FROM zh_terms WHERE headword IN (${placeholders}))
              THEN 1 ELSE 0 END AS m_headword,
         CASE WHEN e.id IN (SELECT entry_id FROM aliases WHERE kind = 'synonym' AND alias IN (${placeholders}))
              THEN 1 ELSE 0 END AS m_synonym,
         CASE WHEN e.id IN (SELECT entry_id FROM aliases WHERE kind = 'gloss' AND alias IN (${placeholders}))
              THEN 1 ELSE 0 END AS m_gloss
       FROM entries e
       WHERE e.lang = ? AND (e.lang != 'hak' OR e.variant = ?)
       AND (
         e.zh_term_id IN (SELECT id FROM zh_terms WHERE headword IN (${placeholders}))
         OR e.id IN (SELECT entry_id FROM aliases WHERE alias IN (${placeholders}))
       )
       ORDER BY e.id`,
    )
    stmt.bind([...variants, ...variants, ...variants, lang, hakkaVariant, ...variants, ...variants])
    const entries: Entry[] = []
    const matchRanks: number[] = []
    while (stmt.step()) {
      const row = stmt.getAsObject() as Record<string, string | number | null>
      const entryId = row.id as number
      const entry = rowToEntry(row, this.getExamples(entryId), this.getAudio(entryId))
      entries.push(entry)
      matchRanks.push(
        computeMatchRank(entry.lang, row.m_headword === 1, row.m_synonym === 1, row.m_gloss === 1),
      )
    }
    stmt.free()

    const order = entries.map((_, i) => i)
    order.sort((i, j) => {
      const rankDiff = matchRanks[i] - matchRanks[j]
      if (rankDiff !== 0) return rankDiff
      return registerWeight(entries[i].registerTag) - registerWeight(entries[j].registerTag)
    })
    return order.map((i) => entries[i])
  }

  /** Looks up one specific favorited card by the key from entryKey(). Returns
   * null if it no longer exists (e.g. dropped in a later dictionary.sqlite
   * rebuild) — callers should treat that as "quietly skip", not an error. */
  getEntryByKey(key: string): Entry | null {
    const parts = key.split('|')
    // guards against stale localStorage favorites saved under an older key
    // format (e.g. a plain search term, from before favorites were per-card)
    if (parts.length !== 4) return null
    const [lang, variant, script, pronunciation1] = parts
    const stmt = this.db.prepare(
      `SELECT * FROM entries
       WHERE lang = ? AND COALESCE(variant, '') = ? AND script = ? AND COALESCE(pronunciation_1, '') = ?
       LIMIT 1`,
    )
    stmt.bind([lang, variant, script, pronunciation1])
    const found = stmt.step()
    if (!found) {
      stmt.free()
      return null
    }
    const row = stmt.getAsObject() as Record<string, string | number | null>
    const entryId = row.id as number
    const entry = rowToEntry(row, this.getExamples(entryId), this.getAudio(entryId))
    stmt.free()
    return entry
  }

  private getExamples(entryId: number): Example[] {
    const stmt = this.db.prepare('SELECT * FROM examples WHERE entry_id = :eid ORDER BY id')
    stmt.bind({ ':eid': entryId })
    const out: Example[] = []
    while (stmt.step()) {
      const row = stmt.getAsObject() as Record<string, string | number | null>
      out.push({
        id: row.id as number,
        exampleText: row.example_text as string,
        exampleRomanization: row.example_romanization as string | null,
        exampleTranslationZh: row.example_translation_zh as string | null,
        audioUrl: row.audio_url as string | null,
      })
    }
    stmt.free()
    return out
  }

  private getAudio(entryId: number): WordAudio[] {
    const stmt = this.db.prepare('SELECT * FROM word_audio WHERE entry_id = :eid ORDER BY id')
    stmt.bind({ ':eid': entryId })
    const out: WordAudio[] = []
    while (stmt.step()) {
      const row = stmt.getAsObject() as Record<string, string | number | null>
      out.push({ id: row.id as number, audioUrl: row.audio_url as string })
    }
    stmt.free()
    return out
  }
}

let sqlPromise: Promise<SqlJsStatic> | null = null
let clientPromise: Promise<DictionaryClient> | null = null

// GitHub Pages sends `Cache-Control: max-age=600` on dictionary.sqlite and
// doesn't support custom response headers, so the browser's own HTTP cache
// re-downloads the full ~14MB (gzipped) file on almost every repeat visit.
// This keeps our own longer-lived copy in IndexedDB, keyed by the file's
// ETag, so a revisit only needs a tiny HEAD request unless the dictionary
// actually changed.
const CACHE_DB_NAME = 'words-lookup-db-cache'
const CACHE_STORE_NAME = 'files'
const CACHE_KEY = 'dictionary.sqlite'

interface CachedFile {
  etag: string
  bytes: ArrayBuffer
}

function openCacheDb(): Promise<IDBDatabase | null> {
  return new Promise((resolve) => {
    if (!('indexedDB' in window)) {
      resolve(null)
      return
    }
    const req = indexedDB.open(CACHE_DB_NAME, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(CACHE_STORE_NAME)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => resolve(null)
  })
}

function readCachedFile(idb: IDBDatabase | null): Promise<CachedFile | null> {
  if (!idb) return Promise.resolve(null)
  return new Promise((resolve) => {
    const req = idb.transaction(CACHE_STORE_NAME, 'readonly').objectStore(CACHE_STORE_NAME).get(CACHE_KEY)
    req.onsuccess = () => resolve((req.result as CachedFile | undefined) ?? null)
    req.onerror = () => resolve(null)
  })
}

function writeCachedFile(idb: IDBDatabase | null, file: CachedFile): void {
  if (!idb) return
  // Fire-and-forget — a failed write just means next visit re-downloads.
  idb.transaction(CACHE_STORE_NAME, 'readwrite').objectStore(CACHE_STORE_NAME).put(file, CACHE_KEY)
}

async function loadClient(): Promise<DictionaryClient> {
  if (!sqlPromise) {
    sqlPromise = initSqlJs({ locateFile: (file) => `${import.meta.env.BASE_URL}${file}` })
  }
  const [SQL, idb] = await Promise.all([sqlPromise, openCacheDb()])
  const url = `${import.meta.env.BASE_URL}dictionary.sqlite`

  const [cached, currentEtag] = await Promise.all([
    readCachedFile(idb),
    fetch(url, { method: 'HEAD', cache: 'no-store' })
      .then((r) => r.headers.get('etag'))
      .catch(() => null),
  ])

  if (cached && currentEtag && cached.etag === currentEtag) {
    return new DictionaryClient(new SQL.Database(new Uint8Array(cached.bytes)))
  }

  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`Failed to fetch dictionary.sqlite: ${res.status}`)
  }
  const buf = await res.arrayBuffer()
  const etag = res.headers.get('etag')
  if (etag) writeCachedFile(idb, { etag, bytes: buf })
  return new DictionaryClient(new SQL.Database(new Uint8Array(buf)))
}

type Status = 'loading' | 'ready' | 'error'

export function useDictionary(): { db: DictionaryClient | null; status: Status } {
  const [state, setState] = useState<{ db: DictionaryClient | null; status: Status }>({
    db: null,
    status: 'loading',
  })

  useEffect(() => {
    let cancelled = false
    if (!clientPromise) clientPromise = loadClient()
    clientPromise
      .then((db) => {
        if (!cancelled) setState({ db, status: 'ready' })
      })
      .catch((err) => {
        console.error('Failed to load dictionary database', err)
        if (!cancelled) setState({ db: null, status: 'error' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
