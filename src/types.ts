export type LangCode = 'yue' | 'nan' | 'hak'
export type HakkaVariant = 'hailu' | 'sixian'

export interface Example {
  id: number
  exampleText: string
  exampleTranslationZh: string | null
  audioUrl: string | null
}

export interface WordAudio {
  id: number
  audioUrl: string
}

export interface Entry {
  id: number
  zhTermId: number
  lang: LangCode
  variant: HakkaVariant | null
  script: string
  pronunciation1: string | null
  pronunciation2: string | null
  definition: string | null
  registerTag: string | null
  sourceName: string
  sourceUrl: string
  licenseNote: string
  examples: Example[]
  audio: WordAudio[]
}
