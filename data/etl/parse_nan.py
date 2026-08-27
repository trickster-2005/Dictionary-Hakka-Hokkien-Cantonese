"""Parses data/raw/kautian.ods — the official 教育部臺灣台語常用詞辭典 export,
downloaded directly from the MOE site (not g0v's moedict-data-twblg JSON
mirror) — into normalized entry dicts.

Multi-sheet workbook, linked by numeric ids. Note: read_ods_rows() has to
pull these ids from the ODS office:value attribute, since a purely-numeric
cell has no <text:p> — without that fix every id column here reads back as
an empty string (see IMPLEMENTATION_NOTES.md).

  詞目            headword: 詞目id, 詞目類型, 漢字, 羅馬字, 分類,
                  羅馬字音檔檔名. 詞目類型 spans five categories (主詞目 /
                  臺華共同詞 / 單字不成詞者 / 近反義詞不單列詞目者 / 附錄) —
                  all included uniformly. g0v's JSON export only ever
                  carried 主詞目, which is exactly why searching e.g. "繁華"
                  (臺華共同詞: shares written form/meaning with Mandarin, no
                  separate 義項) came up empty there.
  義項            senses, keyed by 詞目id + 義項id: 詞性, 解說. A headword can
                  have several; each becomes one "「詞性」解說" line in the
                  entry's definition (三 categories above never have any).
  例句            examples, keyed by 詞目id + 義項id: 漢字, 羅馬字, 華語,
                  音檔檔名 (audio filename intentionally unused for now — see
                  IMPLEMENTATION_NOTES.md on why 台語 audio isn't wired up).
  詞目tuì詞目近義   headword-level synonyms (詞目id <-> 對應詞目id) ->
                  strong_aliases (kind='synonym', union-find eligible — see
                  build_db.py). Listed one-directional in the source; unioned
                  both ways here so search works from either headword.
  義項tuì詞目近義   sense-level synonyms (義項id -> 對應詞目id) -> aliases
                  (kind='gloss', direct-only — NOT fed into strong_aliases).
                  Deliberately kept out of the union-find graph: unioning at
                  sense granularity would let one sense of a polysemous word
                  drag unrelated entries into the same component, the same
                  class of bug as 1.15's 牽手 case.
"""
from pathlib import Path
from urllib.parse import quote

from _common import extract_glosses, read_ods_rows

RAW_PATH = Path(__file__).resolve().parent.parent / "raw" / "kautian.ods"

SOURCE_NAME = "教育部臺灣台語常用詞辭典"
LICENSE_NOTE = (
    "辭典本文著作權為教育部所有,依創用CC 姓名標示-禁止改作 3.0 台灣授權條款釋出;"
    "本站僅重新排版供查詢使用,未更動釋義文字。"
)

NO_SENSE_NOTES = {
    "臺華共同詞": "臺華共同詞,與華語用字、意思相同。",
    "單字不成詞者": "單字,不單獨成詞。",
    "近反義詞不單列詞目者": "僅作為其他詞目的近義詞或反義詞收錄,未獨立列出釋義。",
}


def _source_url(headword: str) -> str:
    # Confirmed by driving the site's own "用臺灣台語查詞目" search form —
    # dict-twblg.json's old `id` field never matched sutian's internal entry
    # ids, and kautian.ods's own 詞目id has no confirmed relationship to them
    # either, so a search-by-headword URL is the only reliably-correct link.
    return f"https://sutian.moe.edu.tw/zh-hant/tshiau/?lui=tai_su&tsha={quote(headword)}"


def _sheet(sheet_name: str):
    rows = read_ods_rows(RAW_PATH, sheet_name=sheet_name)
    header, data = rows[0], rows[1:]
    index = {name: i for i, name in enumerate(header)}

    def get(row: list[str], col: str) -> str:
        i = index.get(col)
        if i is None or i >= len(row):
            return ""
        return row[i].strip()

    return data, get


def parse():
    term_data, term_get = _sheet("詞目")
    terms: dict[str, dict] = {}
    for row in term_data:
        term_id = term_get(row, "詞目id")
        script = term_get(row, "漢字")
        if not term_id or not script:
            continue
        terms[term_id] = {
            "type": term_get(row, "詞目類型"),
            "script": script,
            "pron": term_get(row, "羅馬字"),
            "category": term_get(row, "分類"),
        }

    sense_data, sense_get = _sheet("義項")
    senses_by_term: dict[str, list[dict]] = {}
    sense_term_of: dict[str, str] = {}  # 義項id -> 詞目id, for 義項tuì詞目近義 below
    for row in sense_data:
        term_id = sense_get(row, "詞目id")
        sense_id = sense_get(row, "義項id")
        if not term_id or not sense_id:
            continue
        sense_term_of[sense_id] = term_id
        senses_by_term.setdefault(term_id, []).append({
            "sense_id": sense_id,
            "pos": sense_get(row, "詞性"),
            "def": sense_get(row, "解說"),
        })

    example_data, example_get = _sheet("例句")
    examples_by_sense: dict[tuple[str, str], list[dict]] = {}
    for row in example_data:
        term_id = example_get(row, "詞目id")
        sense_id = example_get(row, "義項id")
        text = example_get(row, "漢字")
        if not term_id or not sense_id or not text:
            continue
        examples_by_sense.setdefault((term_id, sense_id), []).append({
            "text": text,
            "romanization": example_get(row, "羅馬字") or None,
            "translation_zh": example_get(row, "華語") or None,
        })

    hw_syn_data, hw_syn_get = _sheet("詞目tuì詞目近義")
    hw_synonyms: dict[str, set[str]] = {}
    for row in hw_syn_data:
        a_id, b_id = hw_syn_get(row, "詞目id"), hw_syn_get(row, "對應詞目id")
        if not a_id or not b_id or a_id not in terms or b_id not in terms:
            continue
        hw_synonyms.setdefault(a_id, set()).add(terms[b_id]["script"])
        hw_synonyms.setdefault(b_id, set()).add(terms[a_id]["script"])

    sense_syn_data, sense_syn_get = _sheet("義項tuì詞目近義")
    sense_synonyms: dict[str, set[str]] = {}  # term_id -> glosses from any of its senses
    for row in sense_syn_data:
        term_id = sense_term_of.get(sense_syn_get(row, "義項id"))
        target_id = sense_syn_get(row, "對應詞目id")
        if not term_id or not target_id or target_id not in terms:
            continue
        sense_synonyms.setdefault(term_id, set()).add(terms[target_id]["script"])

    rows_out = []
    for term_id, term in terms.items():
        headword = term["script"]
        senses = senses_by_term.get(term_id, [])

        def_lines = []
        examples: list[dict] = []
        glosses: set[str] = set()
        for s in senses:
            if s["def"]:
                pos = s["pos"]
                def_lines.append(f"「{pos}」{s['def']}" if pos else s["def"])
                # kautian.ods's 解說 is often "短義。分類標籤。完整說明。" (e.g.
                # 阿爸's is "爸爸。稱謂。子女對父親的稱呼。") — extract_glosses
                # rejects the whole string once a second 。 shows up, so only
                # the clean first clause goes in; the category label/longer
                # explanation after it was never a synonym candidate anyway.
                glosses.update(extract_glosses(s["def"].split("。", 1)[0], headword))
            examples.extend(examples_by_sense.get((term_id, s["sense_id"]), []))

        if def_lines:
            definition = "\n".join(def_lines)
        else:
            definition = NO_SENSE_NOTES.get(term["type"])

        glosses.update(sense_synonyms.get(term_id, set()))
        strong_aliases = hw_synonyms.get(term_id, set())

        rows_out.append({
            "headword": headword,
            "lang": "nan",
            "variant": None,
            "script": headword,
            "pronunciation_1": term["pron"] or None,
            "pronunciation_2": None,
            "definition": definition,
            "register_tag": term["category"] or None,
            "source_name": SOURCE_NAME,
            "source_url": _source_url(headword),
            "license_note": LICENSE_NOTE,
            "aliases": sorted(g for g in glosses if g and g != headword),
            "strong_aliases": sorted(a for a in strong_aliases if a and a != headword),
            "examples": [
                {
                    "text": e["text"],
                    "romanization": e["romanization"],
                    "translation_zh": e["translation_zh"],
                    "audio_url": None,
                }
                for e in examples
            ],
            "audio": [],
        })
    return rows_out


if __name__ == "__main__":
    result = parse()
    print(f"Parsed {len(result)} Taiwanese Hokkien entries")
