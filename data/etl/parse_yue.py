"""Parses data/raw/粵典辭典資料.csv (words.hk full export) into normalized entry dicts.

The content column uses a small markup:
    (pos:X)(label:Y)...
    <explanation>
    yue:...
    eng:...
    <eg>
    yue:... (example sentence, jyutping usually inline in parens)
    eng:... (English translation)

Only rows with status == 'OK' are kept (excludes entries flagged "未經覆核，
可能有錯漏" / unreviewed-may-contain-errors). The CSV's separate 已公開/未公開
column looked like a "is this live on the site" flag but isn't — plenty of
completely ordinary, clearly-published words (嗅, 坦克, 地質, 六四...) are
marked 未公開, so filtering on it was silently dropping ~72% of otherwise-fine
entries. Confirmed by the user noticing 六四 (which *is* on the live site)
couldn't be found here.

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
    "詞典內容版權屬 Hong Kong Lexicography Limited 所有,採"
    "Non-Commercial Open Data License 1.0 授權,非商業用途下可複製、修改、發佈、"
    "再分發;本專案為非商業性質,僅供個人學習交流使用。"
    "詳見 https://words.hk/base/hoifong/"
)

POS_RE = re.compile(r"\(pos:([^)]*)\)")
LABEL_RE = re.compile(r"\(label:([^)]*)\)")
SIM_RE = re.compile(r"\(sim:([^)]*)\)")
# "#X" at the start of a yue: explanation means "same as X" — words.hk's own
# cross-reference convention, e.g. 抽煙's definition is literally "#吸煙；...".
# High-confidence enough to treat as a strong (transitively-linked) synonym.
HASH_REF_RE = re.compile(r"^#([^；;、,，。]+)")

# "即係" ("that is/means") directly followed by exactly one #-linked
# cross-reference, appearing *anywhere* in the explanation, not just at the
# very start — e.g. 他們's "即係#佢哋" or 乞丐's "即係#乞兒". Two constraints,
# both found necessary by checking real matches against the full CSV rather
# than a handful of hand-picked examples:
#   - Only one word, not a chain: 打卡's "即係#剪#頭髮" is a single compound
#     phrase assembled from two hyperlinked morphemes ("cut" + "hair"), not
#     two separate synonyms of 打卡 — an earlier version that chained
#     consecutive #words (with an optional 或/或者/、 between them) split
#     phrases like this into bogus glosses. 薪水's genuine two-way
#     "即係#人工 或者#糧" is an accepted casualty of dropping this — telling
#     "compound phrase" and "list of alternatives" apart isn't reliable from
#     the punctuation alone, so the safe rule is just one word.
#   - The clause must end right after that word (only trailing whitespace
#     before a real terminator: ，。；！？） or end of string) — 猶太's
#     "同#猶太人 有關" or 外圍賽's antonym-flavoured "分成外圍賽同#決賽週"
#     would otherwise match "猶太人"/"決賽週" as if they were declared
#     equal, when the text is actually saying "related to X" or listing two
#     *different* things.
# No recursion into the linked entry's own text — just what's already
# sitting in this row's own content.
#
# "同" ("same as") was considered as a second trigger alongside "即係" but
# rejected after sampling real matches: even with both constraints
# above, roughly half of "同#X" matches in the actual data are false
# positives (唱片 "同#光碟" — record and CD just happen to share a measure
# word; 外圍賽 "同#決賽週" — qualifiers and finals are different, contrasted
# stages, not synonyms; 北歐 "同#丹麥" — Denmark is one country *within*
# Northern Europe, not a synonym of it; 人馬 "同#馬" — 人馬 is "people and
# horses"/troops, not literally "horse"). "同" is too grammatically
# overloaded in Cantonese (and/with/related-to/compared-to/same-as) for
# pattern matching alone to tell the "same as" sense apart from the rest;
# "即係" doesn't have that ambiguity, which is why matches sampled against
# it were uniformly clean.
JIHAI_RE = re.compile(r"即係#([^\s#，。；！？、）)]+)(?=\s*(?:[，。；！？）)]|$))")


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
    # Most entries open with an explicit <explanation> tag, but some (e.g.
    # "六四") put a first yue:/eng: pair directly after the (pos:...) header,
    # then "----", *then* <explanation> for a second sense — with section
    # starting at None, that first line has nowhere to land and silently
    # vanishes. Starting in "explanation" mode already fixes that; the
    # explicit tag (when present) is then just a harmless no-op re-set.
    section = "explanation"
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

    for part in definition_parts:
        strong_aliases.extend(JIHAI_RE.findall(part))

    strong_aliases = [a for a in dict.fromkeys(strong_aliases) if a and a != headword]
    return register_tag, definition, examples, glosses, strong_aliases


def parse():
    rows_out = []
    with open(RAW_PATH, encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) != 6:
                continue
            _id, headword_field, content, _blank, status, _visibility = row
            if status != "OK":
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
