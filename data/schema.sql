CREATE TABLE zh_terms (
  id INTEGER PRIMARY KEY,
  headword TEXT NOT NULL UNIQUE
);

CREATE TABLE entries (
  id INTEGER PRIMARY KEY,
  zh_term_id INTEGER NOT NULL REFERENCES zh_terms(id),
  lang TEXT NOT NULL,              -- 'yue' | 'nan' | 'hak'
  variant TEXT,                    -- hak only: 'hailu' | 'sixian'
  script TEXT NOT NULL,
  pronunciation_1 TEXT,
  pronunciation_2 TEXT,
  definition TEXT,
  register_tag TEXT,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  license_note TEXT NOT NULL
);

CREATE TABLE examples (
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES entries(id),
  example_text TEXT NOT NULL,
  example_translation_zh TEXT,
  audio_url TEXT
);

CREATE TABLE word_audio (
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES entries(id),
  audio_url TEXT NOT NULL
);

-- Alternate search keys for an entry: short Mandarin glosses pulled from the
-- entry's own definition (e.g. Taiwanese "食薰" has def "抽煙、吸煙。" -> aliases
-- "抽煙" and "吸煙"), so searching a Mandarin word finds dialect entries whose
-- native headword is completely different text.
CREATE TABLE aliases (
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES entries(id),
  alias TEXT NOT NULL
);

CREATE INDEX idx_entries_zh_term ON entries(zh_term_id, lang);
CREATE INDEX idx_examples_entry ON examples(entry_id);
CREATE INDEX idx_word_audio_entry ON word_audio(entry_id);
CREATE INDEX idx_aliases_alias ON aliases(alias);
CREATE INDEX idx_aliases_entry ON aliases(entry_id);
