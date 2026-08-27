"""Parses data/raw/客語典文字資料.ods — the raw spreadsheet behind
g0v/moedict-data-hakka, richer than that repo's own processed dict-hakka.json
(which drops the 對應國語/近義詞 columns and the plain-text accent readings
entirely) — into normalized entry dicts for the 海陸 and 四縣 accents.

Columns used (see _common.read_ods_rows for how .ods gets read without a
third-party dependency):
  詞目                 headword
  詞性                 part of speech -> shown as a small tag (register_tag slot)
  海陸腔音讀/四縣腔音讀   pronunciation, already in the official 通用拼音調值標記法
                       (plain digits, e.g. "a24 ba24") — published as-is, no
                       guessing/conversion needed (unlike the old dict-hakka.json
                       pipeline, which had to reverse-engineer this from
                       superscript tone marks via a partial lookup table)
  釋義                 definition, often several numbered senses in one cell
                       ("1. ... \n2. ..."), with example sentences embedded
                       inline as "例：...。（Mandarin translation）" — pulled
                       back out into proper examples[] below
  對應國語             corresponding Mandarin word(s) — the strongest
                       cross-language signal available; tier-1 search alias
                       (kind='synonym', also union-find-linked — see build_db.py)
  近義詞               Hakka-internal near-synonyms, e.g. "【大伯】、2.【老伯】";
                       tier-2 search alias (kind='gloss', direct-only)
"""
import re
from pathlib import Path
from urllib.parse import quote

from _common import read_ods_rows

RAW_PATH = Path(__file__).resolve().parent.parent / "raw" / "客語典文字資料.ods"

SOURCE_NAME = "教育部臺灣客語辭典"
LICENSE_NOTE = (
    "辭典本文著作權為教育部所有,依創用CC 姓名標示-禁止改作 3.0 台灣授權條款釋出;"
    "本站僅重新排版供查詢使用,未更動釋義文字。"
)
# hakkadict.moe.edu.tw's own search is POST/session-based and ignores a GET
# query string on /search_list/ — but its homepage reads ?keyword= and
# pre-fills the search box (confirmed by loading the page and reading the
# input's value), without auto-submitting. So this at least saves the user
# from re-typing the word; they still need one click on "檢索" themselves.

ACCENT_COLUMNS = {"hailu": "海陸腔音讀", "sixian": "四縣腔音讀"}

BRACKET_RE = re.compile(r"【([^】]+)】")
SPLIT_RE = re.compile(r"[、,，]")
EXAMPLE_RE = re.compile(r"例[：:]\s*([^。]+)。\s*(?:[（(]([^）)]*)[）)])?")


def _split_clean(text: str, headword: str) -> list[str]:
    return [p.strip() for p in SPLIT_RE.split(text) if p.strip() and p.strip() != headword]


def _extract_examples(def_text: str):
    """Pulls "例：X。（Y）" out of a definition line, returning the line with
    that segment removed plus any example it found."""
    examples = []

    def repl(m: re.Match) -> str:
        text = m.group(1).strip()
        translation = (m.group(2) or "").strip() or None
        if text:
            examples.append({"text": text, "translation_zh": translation, "audio_url": None})
        return ""

    cleaned = EXAMPLE_RE.sub(repl, def_text).strip()
    return cleaned, examples


def parse():
    rows = read_ods_rows(RAW_PATH)
    header, data_rows = rows[0], rows[1:]
    col_index = {name: i for i, name in enumerate(header)}

    def get(row: list[str], col: str) -> str:
        i = col_index.get(col)
        if i is None or i >= len(row):
            return ""
        return row[i].strip()

    rows_out = []
    for row in data_rows:
        headword = get(row, "詞目")
        if not headword or "□" in headword:
            continue  # unrecoverable placeholder glyph, not a usable search term

        raw_definition = get(row, "釋義")
        if not raw_definition:
            continue

        def_lines = []
        examples = []
        for line in raw_definition.split("\n"):
            cleaned, line_examples = _extract_examples(line)
            if cleaned:
                def_lines.append(cleaned)
            examples.extend(line_examples)
        definition = "\n".join(def_lines) or None
        if definition is None:
            continue

        mandarin = _split_clean(get(row, "對應國語"), headword)
        near_synonyms = [m for m in BRACKET_RE.findall(get(row, "近義詞")) if m and m != headword]
        pos = get(row, "詞性") or None

        for variant, col in ACCENT_COLUMNS.items():
            pron = get(row, col)
            if not pron:
                continue  # no recorded reading for this accent on this word
            rows_out.append({
                "headword": headword,
                "lang": "hak",
                "variant": variant,
                "script": headword,
                "pronunciation_1": pron,
                "pronunciation_2": None,
                "definition": definition,
                "register_tag": pos,
                "source_name": SOURCE_NAME,
                "source_url": f"https://hakkadict.moe.edu.tw/?keyword={quote(headword)}",
                "license_note": LICENSE_NOTE,
                "aliases": near_synonyms,
                "strong_aliases": mandarin,
                "examples": examples,
                "audio": [],
            })
    return rows_out


if __name__ == "__main__":
    result = parse()
    print(f"Parsed {len(result)} Hakka entries (海陸+四縣)")
