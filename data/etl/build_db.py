"""Builds public/dictionary.sqlite from data/schema.sql + the language parsers.

Run via `npm run build:data`, or directly: `python data/etl/build_db.py`.
Safe to re-run — always rebuilds the sqlite file from scratch.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_moedict
import parse_yue
import parse_nan
import parse_hak
from _common import UnionFind

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "data" / "schema.sql"
DB_PATH = PROJECT_ROOT / "public" / "dictionary.sqlite"


def build():
    print("Checking source data...")
    fetch_moedict.fetch()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    term_ids: dict[str, int] = {}

    def get_term_id(headword: str) -> int:
        if headword not in term_ids:
            cur = conn.execute("INSERT INTO zh_terms (headword) VALUES (?)", (headword,))
            term_ids[headword] = cur.lastrowid
        return term_ids[headword]

    print("Parsing Cantonese (words.hk)...")
    yue_rows = parse_yue.parse()
    print(f"  {len(yue_rows)} entries")

    print("Parsing Taiwanese Hokkien (moedict-data-twblg)...")
    nan_rows = parse_nan.parse()
    print(f"  {len(nan_rows)} entries")

    print("Parsing Hakka (moedict-data-hakka)...")
    hak_rows = parse_hak.parse()
    print(f"  {len(hak_rows)} entries")

    all_rows = yue_rows + nan_rows + hak_rows

    # Curated synonym signals (Cantonese sim:/#, Taiwanese synonyms) link
    # entries transitively: if A ~ C and B ~ C, A and B become mutually
    # findable even though neither mentions the other directly. Restricted to
    # these "strong" edges only — generic short-gloss aliases stay direct-only
    # so a common word like "吃" doesn't pull unrelated entries together.
    uf = UnionFind()
    for row in all_rows:
        for strong in row.get("strong_aliases", []):
            uf.union(row["headword"], strong)

    component_members: dict[str, set[str]] = {}
    for row in all_rows:
        component_members.setdefault(uf.find(row["headword"]), set()).add(row["headword"])
        for strong in row.get("strong_aliases", []):
            component_members.setdefault(uf.find(strong), set()).add(strong)

    # A handful of polysemous hub words (e.g. "金" — gold/money/a surname/...)
    # chain unrelated senses together transitively until the component covers
    # dozens of unconnected concepts (confirmed empirically: 27778 components,
    # only 103 exceed size 8, but those 103 are genuinely garbage — "金"
    # dragged in "水", "説謊", "季節"...). Cap membership size so those collapse
    # back to direct-only aliases instead of polluting search results, while
    # the ~99.6% of components that stay small (the 抽煙/食煙/吸煙 case this
    # was built for) keep the transitive expansion.
    MAX_COMPONENT_SIZE = 8

    def expanded_aliases(row: dict) -> list[str]:
        direct = set(row.get("aliases", []))
        members = component_members.get(uf.find(row["headword"]), set())
        if len(members) <= MAX_COMPONENT_SIZE:
            direct |= members - {row["headword"]}
        return sorted(direct)

    n_strong_edges = sum(len(r.get("strong_aliases", [])) for r in all_rows)
    n_capped = sum(1 for m in component_members.values() if len(m) > MAX_COMPONENT_SIZE)
    print(
        f"  {n_strong_edges} strong synonym edges -> {len(component_members)} components "
        f"({n_capped} over size {MAX_COMPONENT_SIZE}, capped to direct-only)"
    )

    for row in all_rows:
        term_id = get_term_id(row["headword"])
        cur = conn.execute(
            """INSERT INTO entries
               (zh_term_id, lang, variant, script, pronunciation_1, pronunciation_2,
                definition, register_tag, source_name, source_url, license_note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                term_id,
                row["lang"],
                row["variant"],
                row["script"],
                row["pronunciation_1"],
                row["pronunciation_2"],
                row["definition"],
                row["register_tag"],
                row["source_name"],
                row["source_url"],
                row["license_note"],
            ),
        )
        entry_id = cur.lastrowid
        for ex in row["examples"]:
            conn.execute(
                """INSERT INTO examples (entry_id, example_text, example_translation_zh, audio_url)
                   VALUES (?, ?, ?, ?)""",
                (entry_id, ex["text"], ex.get("translation_zh"), ex.get("audio_url")),
            )
        for a in row["audio"]:
            conn.execute(
                "INSERT INTO word_audio (entry_id, audio_url) VALUES (?, ?)",
                (entry_id, a["audio_url"]),
            )
        for alias in expanded_aliases(row):
            conn.execute(
                "INSERT INTO aliases (entry_id, alias) VALUES (?, ?)",
                (entry_id, alias),
            )

    conn.commit()
    n_terms = conn.execute("SELECT COUNT(*) FROM zh_terms").fetchone()[0]
    n_entries = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    n_aliases = conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
    conn.close()
    print(f"Built {DB_PATH} — {n_terms} terms, {n_entries} entries, {n_aliases} aliases")


if __name__ == "__main__":
    build()
