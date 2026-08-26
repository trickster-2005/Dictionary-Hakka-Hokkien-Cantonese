"""Parses data/raw/dict-hakka.json (g0v-processed 教育部臺灣客家語常用詞辭典) into
normalized entry dicts for the 海陸 and 四縣 accents.

The `pinyin` field packs all six accents into one string, e.g.:
    "四⃞gia²⁴ 海⃞gia⁵³ 平⃞gia²⁴ 安⃞gia⁵⁵"
Segments are space-separated, each starting with a one-character accent marker
(四=四縣 海=海陸 大=大埔 平=饒平 安=詔安 南=南四縣) followed by U+20DE, then the
romanization with tone written as superscript digits. Only 四/海 are used here.

data/raw/海陸腔.csv converts "syllable+tone-value" (e.g. "gia24") to the
official 教育部客語拼音 suffix notation (e.g. "giaˋ"). Its coverage is partial
(883 syllables), so unmatched syllables fall back to a tone-value-only
heuristic (majority vote across the table), and failing that keep the raw
superscript form rather than guessing wrong.
"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

from _common import extract_glosses, parse_bracketed_example

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
DICT_PATH = RAW_DIR / "dict-hakka.json"
TONE_TABLE_PATH = RAW_DIR / "海陸腔.csv"

SOURCE_NAME = "教育部臺灣客語辭典"
LICENSE_NOTE = (
    "辭典本文著作權為教育部所有,依創用CC 姓名標示-禁止改作 3.0 台灣授權條款釋出;"
    "本站僅重新排版供查詢使用,未更動釋義文字。"
)
SOURCE_URL = "https://hakkadict.moe.edu.tw/"
# g0v/moedict-data-hakka's mp3-urls.txt points at hakka.dict.edu.tw, which no
# longer resolves to a live server (confirmed: DNS resolves fine, but every
# connection attempt times out — the host has been retired). The live site
# (hakkadict.moe.edu.tw) does serve per-word audio, but only from a dynamic
# per-entry numeric id that isn't present anywhere in this JSON export, so
# there's no way to construct a working URL from what we have. Shipping the
# old dead links would be worse than no button, so this pass has no Hakka
# word_audio until a real source is found.

ACCENT_MARKERS = {"四": "sixian", "海": "hailu"}  # scope: only these two this pass

SUPERSCRIPT_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
SYLLABLE_RE = re.compile(r"([a-zA-Z]+)([⁰¹²³⁴⁵⁶⁷⁸⁹]+)")
SEGMENT_RE = re.compile(r"([四海大平安南])⃞(\S+)")


def _load_tone_tables():
    exact_map: dict[str, str] = {}
    tone_votes: dict[str, Counter] = {}
    with open(TONE_TABLE_PATH, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 3:
                continue
            col1, col3 = row[0].strip(), row[2].strip()
            if not col1 or not col3:
                continue
            exact_map[col1] = col3
            m = re.match(r"^([a-zA-Z]+)(\d+)$", col1)
            if m and col3.startswith(m.group(1)):
                tone = m.group(2)
                suffix = col3[len(m.group(1)):]
                tone_votes.setdefault(tone, Counter())[suffix] += 1
    tone_fallback = {tone: counter.most_common(1)[0][0] for tone, counter in tone_votes.items()}
    return exact_map, tone_fallback


def _convert_segment(text: str, exact_map: dict, tone_fallback: dict) -> str:
    # Syllables are packed with no separator in the source ("gia²⁴sa¹¹"), but
    # hakkadict.moe.edu.tw's own results page renders these space-separated
    # ("pen rhiuˋ") — match that instead of leaving syllables run together.
    parts = []
    for syllable, sup_tone in SYLLABLE_RE.findall(text):
        tone = sup_tone.translate(SUPERSCRIPT_MAP)
        key = syllable + tone
        if key in exact_map:
            parts.append(exact_map[key])
            continue
        suffix = tone_fallback.get(tone)
        parts.append(syllable + suffix if suffix is not None else syllable + sup_tone)
    return " ".join(parts) if parts else text


def _parse_pinyin(pinyin: str, exact_map: dict, tone_fallback: dict):
    result = {"hailu": None, "sixian": None}
    for marker, raw in SEGMENT_RE.findall(pinyin or ""):
        variant = ACCENT_MARKERS.get(marker)
        if variant is None:
            continue
        result[variant] = _convert_segment(raw, exact_map, tone_fallback)
    return result


def parse():
    exact_map, tone_fallback = _load_tone_tables()
    with open(DICT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    rows_out = []
    for item in data:
        headword = item.get("title")
        if not headword or "□" in headword:
            continue  # unrecoverable placeholder glyph, not a usable search term

        for heteronym in item.get("heteronyms", []):
            pronunciations = _parse_pinyin(heteronym.get("pinyin", ""), exact_map, tone_fallback)
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
            definition = "\n".join(def_lines) or None

            for variant in ("hailu", "sixian"):
                pron = pronunciations.get(variant)
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
                    "register_tag": None,
                    "source_name": SOURCE_NAME,
                    "source_url": SOURCE_URL,
                    "license_note": LICENSE_NOTE,
                    "aliases": sorted(glosses),
                    "examples": [
                        {"text": e["text"], "translation_zh": e["translation_zh"], "audio_url": None}
                        for e in examples
                    ],
                    "audio": [],
                })
    return rows_out


if __name__ == "__main__":
    result = parse()
    print(f"Parsed {len(result)} Hakka entries (海陸+四縣)")
