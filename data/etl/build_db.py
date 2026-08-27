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

    print("Parsing Taiwanese Hokkien (kautian.ods)...")
    nan_rows = parse_nan.parse()
    print(f"  {len(nan_rows)} entries")

    print("Parsing Hakka (moedict-data-hakka)...")
    hak_rows = parse_hak.parse()
    print(f"  {len(hak_rows)} entries")

    all_rows = yue_rows + nan_rows + hak_rows

    # Curated synonym signals (Cantonese sim:/#, Taiwanese synonyms, Hakka
    # 對應國語/近義詞) link entries transitively: if A ~ C and B ~ C, A and B
    # become mutually findable even though neither mentions the other
    # directly. Restricted to these "strong" edges only — generic short-gloss
    # aliases stay direct-only so a common word like "吃" doesn't pull
    # unrelated entries together.
    #
    # Each language gets its own independent UnionFind — a Taiwanese cross-
    # reference should never pull in a Cantonese or Hakka entry (each
    # dictionary's own synonym signal reflects only how *that* language's
    # editors cross-referenced their own entries; treating the three as one
    # combined graph produced results like 牽手 (Taiwanese for "wife") dragging
    # in unrelated Cantonese 老婆/太太/妻子 cards). This also means a headword
    # spelled the same way in two languages for two unrelated senses (e.g.
    # Hakka 牽手 "hold hands" vs Taiwanese 牽手 "wife") can no longer merge into
    # one cluster just because the text happens to match.
    def build_clusters(rows: list[dict]) -> tuple[UnionFind, dict[str, set[str]]]:
        uf = UnionFind()
        for row in rows:
            for strong in row.get("strong_aliases", []):
                uf.union(row["headword"], strong)
        component_members: dict[str, set[str]] = {}
        for row in rows:
            component_members.setdefault(uf.find(row["headword"]), set()).add(row["headword"])
            for strong in row.get("strong_aliases", []):
                component_members.setdefault(uf.find(strong), set()).add(strong)
        return uf, component_members

    clusters_by_lang = {
        "yue": build_clusters(yue_rows),
        "nan": build_clusters(nan_rows),
        "hak": build_clusters(hak_rows),
    }

    # A handful of polysemous hub words (e.g. "金" — gold/money/a surname/...)
    # chain unrelated senses together transitively until the component covers
    # dozens of unconnected concepts within one language. An earlier cap of 8
    # was picked without actually inspecting mid-size components, and turned
    # out to wrongly nuke perfectly good clusters too. Manually inspected the
    # actual size distribution instead: components up to ~70 members are
    # still topically coherent (checked several by hand — "death",
    # "lying/bragging", "face/immediately", "comparison words" clusters all
    # check out), while outliers above that are genuine grab-bags of
    # unrelated senses chained through promiscuous hub characters. 80 sits
    # cleanly between the two. (Calibrated back when clustering was combined
    # across all three languages — components are smaller now that each
    # language is independent, so this cap triggers less often, but the same
    # single-language hub-word risk it guards against still applies.)
    MAX_COMPONENT_SIZE = 80

    def expanded_aliases(row: dict) -> list[tuple[str, str]]:
        # 'synonym' wins over 'gloss' when both point at the same string —
        # it's the more curated signal, so if a word shows up both as a
        # generic short gloss AND a dictionary-tagged synonym, tag it synonym.
        kind_by_alias = {a: "gloss" for a in row.get("aliases", [])}
        # Only a row that itself contributed a strong alias gets to inherit
        # the cluster — otherwise a same-spelled-but-unrelated row elsewhere
        # in the same language would drag this one in by text collision alone.
        if row.get("strong_aliases"):
            uf, component_members = clusters_by_lang[row["lang"]]
            members = component_members.get(uf.find(row["headword"]), set())
            if len(members) <= MAX_COMPONENT_SIZE:
                for a in members - {row["headword"]}:
                    kind_by_alias[a] = "synonym"
        return sorted(kind_by_alias.items())

    n_strong_edges = sum(len(r.get("strong_aliases", [])) for r in all_rows)
    all_component_members = [m for _, cm in clusters_by_lang.values() for m in cm.values()]
    n_capped = sum(1 for m in all_component_members if len(m) > MAX_COMPONENT_SIZE)
    print(
        f"  {n_strong_edges} strong synonym edges -> {len(all_component_members)} components "
        f"(per-language, {n_capped} over size {MAX_COMPONENT_SIZE}, capped to direct-only)"
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
                """INSERT INTO examples
                   (entry_id, example_text, example_romanization, example_translation_zh, audio_url)
                   VALUES (?, ?, ?, ?, ?)""",
                (entry_id, ex["text"], ex.get("romanization"), ex.get("translation_zh"), ex.get("audio_url")),
            )
        for a in row["audio"]:
            conn.execute(
                "INSERT INTO word_audio (entry_id, audio_url) VALUES (?, ?)",
                (entry_id, a["audio_url"]),
            )
        for alias, kind in expanded_aliases(row):
            conn.execute(
                "INSERT INTO aliases (entry_id, alias, kind) VALUES (?, ?, ?)",
                (entry_id, alias, kind),
            )

    conn.commit()
    n_terms = conn.execute("SELECT COUNT(*) FROM zh_terms").fetchone()[0]
    n_entries = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    n_aliases = conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
    conn.close()
    print(f"Built {DB_PATH} — {n_terms} terms, {n_entries} entries, {n_aliases} aliases")


if __name__ == "__main__":
    build()
