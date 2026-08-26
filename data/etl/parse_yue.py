"""Parses data/raw/粵典辭典資料.csv (words.hk full export) into normalized entry dicts.

The content column uses a small markup:
    (pos:X)(label:Y)...
    <explanation>
    yue:...
    eng:...
    <eg>
    yue:... (example sentence, jyutping usually inline in parens)
    eng:... (English translation)

Only rows with status == 'OK' and visibility == '已公開' are kept — the export
is roughly half unreviewed / unpublished community submissions.

words.hk content is "ALL RIGHTS RESERVED. DO NOT DISTRIBUTE" per the CSV's own
header comment — see data/etl/README.md. This script only ever reads the local
CSV; it never uploads or re-publishes it anywhere.
"""
import csv
import re
from pathlib import Path

from _common import extract_glosses

RAW_PATH = Path(__file__).resolve().parent.parent / "raw" / "粵典辭典資料.csv"

SOURCE_NAME = "粵典 words.hk"
LICENSE_NOTE = (
    "詞典內容版權屬 Hong Kong Lexicography Limited 所有,原始匯出檔案標註"
    "「ALL RIGHTS RESERVED. DO NOT DISTRIBUTE」,僅供本機個人查詢使用,"
    "詳見 https://words.hk/base/hoifong/"
)

POS_RE = re.compile(r"\(pos:([^)]*)\)")
LABEL_RE = re.compile(r"\(label:([^)]*)\)")
SIM_RE = re.compile(r"\(sim:([^)]*)\)")
# "#X" at the start of a yue: explanation means "same as X" — words.hk's own
# cross-reference convention, e.g. 抽煙's definition is literally "#吸煙；...".
# High-confidence enough to treat as a strong (transitively-linked) synonym.
HASH_REF_RE = re.compile(r"^#([^；;、,，。]+)")


def _split_headword_field(field: str):
    """'嗅:cau3' -> [('嗅','cau3')]; '瓊:king4,凝:king4' -> [('瓊','king4'),('凝','king4')]
    A syllable can list several alternate pronunciations separated by extra
    colons (e.g. loanwords) — only the first is kept for display.
    """
    variants = []
    for segment in field.split(","):
        if ":" not in segment:
            continue
        headword, rest = segment.split(":", 1)
        headword = headword.strip()
        pron = rest.split(":")[0].strip()
        if headword:
            variants.append((headword, pron))
    return variants


def _parse_content(content: str, headword: str):
    if not content or content.strip() == "未有內容 NO DATA":
        return None, None, [], [], []

    lines = content.split("\n")
    register_tag = None
    pos = None
    strong_aliases: list[str] = []
    if lines:
        labels = LABEL_RE.findall(lines[0])
        if labels:
            register_tag = "、".join(labels)
        pos_match = POS_RE.search(lines[0])
        if pos_match and pos_match.group(1).strip():
            pos = pos_match.group(1).strip()
        strong_aliases.extend(v.strip() for v in SIM_RE.findall(lines[0]) if v.strip())

    definition_parts = []
    zho_parts = []
    examples = []
    section = None
    current_eg = {}

    for raw_line in lines[1:]:
        line = raw_line.strip()
        if line == "<explanation>":
            section = "explanation"
            continue
        if line == "<eg>":
            if current_eg.get("yue"):
                examples.append(current_eg)
            current_eg = {}
            section = "eg"
            continue
        if line.startswith("yue:"):
            text = line[len("yue:"):].strip()
            if section == "explanation":
                if not definition_parts:
                    m = HASH_REF_RE.match(text)
                    if m:
                        strong_aliases.append(m.group(1).strip())
                definition_parts.append(text)
            elif section == "eg":
                current_eg["yue"] = text
            continue
        if line.startswith("zho:"):
            # explicit Mandarin cross-reference, when present — the highest
            # confidence signal we have for "what would someone type in
            # Mandarin to look for this", so it's kept separately from yue:
            # (which is a Cantonese-register explanation, not reliably valid
            # Mandarin wording)
            if section == "explanation":
                zho_parts.append(line[len("zho:"):].strip())
            continue
        if line.startswith("eng:"):
            # only used inside <eg> blocks in this pass
            if section == "eg":
                current_eg["eng"] = line[len("eng:"):].strip()
            continue

    if current_eg.get("yue"):
        examples.append(current_eg)

    definition = " ".join(p for p in definition_parts if p) or None
    if definition and definition.startswith("#"):
        definition = "同「" + definition[1:] + "」"
    if definition and pos:
        definition = f"「{pos}」{definition}"

    glosses: list[str] = []
    for zho in zho_parts:
        m = HASH_REF_RE.match(zho)
        if m:
            strong_aliases.append(m.group(1).strip())
        glosses.extend(extract_glosses(zho.lstrip("#"), headword))

    strong_aliases = [a for a in dict.fromkeys(strong_aliases) if a and a != headword]
    return register_tag, definition, examples, glosses, strong_aliases


def parse():
    rows_out = []
    with open(RAW_PATH, encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) != 6:
                continue
            _id, headword_field, content, _blank, status, visibility = row
            if status != "OK" or visibility != "已公開":
                continue

            variants = _split_headword_field(headword_field)
            if not variants:
                continue

            # zho:/sim:/# cross-references are parsed once per row using the
            # first headword variant as the "is this just the headword"
            # check; good enough since variants of one row share one definition
            register_tag, definition, examples, glosses, strong_aliases = _parse_content(
                content, variants[0][0]
            )
            if definition is None:
                continue

            for headword, pron in variants:
                rows_out.append({
                    "headword": headword,
                    "lang": "yue",
                    "variant": None,
                    "script": headword,
                    "pronunciation_1": pron or None,
                    "pronunciation_2": None,
                    "definition": definition,
                    "register_tag": register_tag,
                    "source_name": SOURCE_NAME,
                    "source_url": f"https://words.hk/zidin/{headword}",
                    "license_note": LICENSE_NOTE,
                    "aliases": [g for g in glosses if g != headword],
                    "strong_aliases": [a for a in strong_aliases if a != headword],
                    "examples": [
                        {"text": eg["yue"], "translation_zh": None, "audio_url": None}
                        for eg in examples
                        if eg.get("yue")
                    ],
                    "audio": [],
                })
    return rows_out


if __name__ == "__main__":
    result = parse()
    print(f"Parsed {len(result)} Cantonese entries")
