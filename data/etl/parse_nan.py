"""Parses data/raw/dict-twblg.json (g0v-processed 教育部臺灣台語常用詞辭典) into
normalized entry dicts.
"""
import json
from pathlib import Path
from urllib.parse import quote

from _common import extract_glosses, parse_bracketed_example

RAW_PATH = Path(__file__).resolve().parent.parent / "raw" / "dict-twblg.json"

SOURCE_NAME = "教育部臺灣台語常用詞辭典"
LICENSE_NOTE = (
    "辭典本文著作權為教育部所有,依創用CC 姓名標示-禁止改作 3.0 台灣授權條款釋出;"
    "本站僅重新排版供查詢使用,未更動釋義文字。"
)


def _source_url(headword: str) -> str:
    # Confirmed by driving the site's own "用臺灣台語查詞目" search form —
    # dict-twblg.json's own `id` field does NOT match sutian's internal entry
    # ids (verified: id "4215" on sutian.moe.edu.tw is a different word than
    # heteronym id "4215" for 朋友), so a search-by-headword URL is the only
    # reliably-correct link.
    return f"https://sutian.moe.edu.tw/zh-hant/tshiau/?lui=tai_su&tsha={quote(headword)}"


def parse():
    with open(RAW_PATH, encoding="utf-8") as f:
        data = json.load(f)

    rows_out = []
    for item in data:
        headword = item.get("title")
        if not headword:
            continue
        for heteronym in item.get("heteronyms", []):
            definitions = heteronym.get("definitions", [])
            if not definitions:
                continue

            def_lines = []
            examples = []
            glosses: set[str] = set()
            for d in definitions:
                if d.get("def"):
                    pos = (d.get("type") or "").strip()
                    def_lines.append(f"「{pos}」{d['def']}" if pos else d["def"])
                    glosses.update(extract_glosses(d["def"], headword))
                for ex in d.get("example", []) or []:
                    text, translation = parse_bracketed_example(ex)
                    if text:
                        examples.append({"text": text, "translation_zh": translation})

            # one sense per line (each may carry its own part-of-speech tag) —
            # the frontend renders \n as line breaks
            definition = "\n".join(def_lines) or None

            # dictionary-curated same-language synonyms, e.g. "㧌" lists "揍" —
            # strong enough to transitively link entries through (see build_db.py)
            strong_aliases = [
                s.strip()
                for s in (heteronym.get("synonyms") or "").split(",")
                if s.strip() and s.strip() != headword
            ]

            rows_out.append({
                "headword": headword,
                "lang": "nan",
                "variant": None,
                "script": headword,
                "pronunciation_1": heteronym.get("trs"),
                "pronunciation_2": None,
                "definition": definition,
                "register_tag": None,  # source has no clean 口語/書面語 signal
                "source_name": SOURCE_NAME,
                "source_url": _source_url(headword),
                "license_note": LICENSE_NOTE,
                "aliases": sorted(glosses),
                "strong_aliases": strong_aliases,
                "examples": [
                    {"text": e["text"], "translation_zh": e["translation_zh"], "audio_url": None}
                    for e in examples
                ],
                "audio": [],
            })
    return rows_out


if __name__ == "__main__":
    result = parse()
    print(f"Parsed {len(result)} Taiwanese Hokkien entries")
