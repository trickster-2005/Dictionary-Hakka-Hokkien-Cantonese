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
              THEN 0 ELSE 1 END AS match_rank
       FROM entries e
       WHERE e.lang = ? AND (e.lang != 'hak' OR e.variant = ?)
       AND (
         e.zh_term_id IN (SELECT id FROM zh_terms WHERE headword IN (${placeholders}))
         OR e.id IN (SELECT entry_id FROM aliases WHERE alias IN (${placeholders}))
       )
       ORDER BY e.id`,
    )
    stmt.bind([...variants, lang, hakkaVariant, ...variants, ...variants])
    const entries: Entry[] = []
    const matchRanks: number[] = []
    while (stmt.step()) {
      const row = stmt.getAsObject() as Record<string, string | number | null>
      const entryId = row.id as number
      entries.push({
        id: entryId,
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
        examples: this.getExamples(entryId),
        audio: this.getAudio(entryId),
      })
      matchRanks.push(row.match_rank as number)
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

  private getExamples(entryId: number): Example[] {
    const stmt = this.db.prepare('SELECT * FROM examples WHERE entry_id = :eid ORDER BY id')
    stmt.bind({ ':eid': entryId })
    const out: Example[] = []
    while (stmt.step()) {
      const row = stmt.getAsObject() as Record<string, string | number | null>
      out.push({
        id: row.id as number,
        exampleText: row.example_text as string,
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

async function loadClient(): Promise<DictionaryClient> {
  if (!sqlPromise) {
    sqlPromise = initSqlJs({ locateFile: (file) => `${import.meta.env.BASE_URL}${file}` })
  }
  const SQL = await sqlPromise
  const res = await fetch(`${import.meta.env.BASE_URL}dictionary.sqlite`)
  if (!res.ok) {
    throw new Error(`Failed to fetch dictionary.sqlite: ${res.status}`)
  }
  const buf = await res.arrayBuffer()
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
