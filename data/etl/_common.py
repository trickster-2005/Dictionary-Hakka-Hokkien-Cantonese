"""Shared helpers for the g0v moedict-derived parsers (parse_nan.py, parse_hak.py)."""
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

_ODS_NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
_ODS_TABLE_NS = _ODS_NS["table"]


def read_ods_rows(path: Path, cap_repeat: int = 40) -> list[list[str]]:
    """Reads the first sheet of a .ods spreadsheet into a list of row value
    lists (first row is the header). No third-party dependency (odfpy etc.)
    needed — .ods is just a zip of XML, and the schema is small enough to
    walk directly.

    `cap_repeat` bounds how many times a single `number-columns-repeated`
    cell gets expanded — real data rows only need a couple dozen columns;
    without a cap, the trailing "rest of the row is empty" cell (routinely
    repeated up to the sheet's max column count, e.g. 16384) would expand
    into thousands of empty strings per row.
    """
    with zipfile.ZipFile(path) as z:
        with z.open("content.xml") as f:
            tree = ET.parse(f)

    table = tree.getroot().find(".//table:table", _ODS_NS)
    rows = table.findall("table:table-row", _ODS_NS)

    def cell_text(cell: ET.Element) -> str:
        paragraphs = cell.findall(".//text:p", _ODS_NS)
        return "\n".join("".join(p.itertext()) for p in paragraphs)

    def expand_row(row: ET.Element) -> list[str]:
        out: list[str] = []
        for cell in row.findall("table:table-cell", _ODS_NS):
            repeat = min(int(cell.get(f"{{{_ODS_TABLE_NS}}}number-columns-repeated", "1")), cap_repeat)
            out.extend([cell_text(cell)] * repeat)
        while out and out[-1] == "":
            out.pop()
        return out

    return [expand_row(r) for r in rows]

_TRAILING_PUNCT_RE = re.compile(r"[。.]+$")
_GLOSS_SPLIT_RE = re.compile(r"[、,，/／;；]")
_DISQUALIFYING_CHARS = set("。：:！!？?「」『』（）()~～ \t")


def extract_glosses(def_text: str | None, headword: str, max_len: int = 6) -> list[str]:
    """Pulls short, clean Mandarin-equivalent search terms out of a dialect
    dictionary's own definition text, e.g. "抽煙、吸煙。" -> ["抽煙", "吸煙"].

    Multiple near-synonyms are commonly joined with 、/,/，, so we split on
    those first rather than rejecting the whole definition outright. Anything
    that still looks like a sentence fragment (leftover punctuation, or just
    too long to plausibly be a single word/short phrase) is dropped — better
    to miss an alias than to index a full sentence as one.

    Critically, a definition with any 。 left over after stripping one
    trailing period is a real (possibly multi-)sentence, not a gloss list —
    reject the whole thing rather than splitting it. Without this, a long
    descriptive definition that happens to contain a 、-separated list
    *within* one clause (e.g. "鱔魚...多分布在印度半島、中國大陸、日本、韓國
    及臺灣等地區。") would have each place name sliced out and indexed as if
    it were a synonym of the headword — confirmed to actually happen:
    searching "日本" was turning up 鱔魚 (a swamp eel) for exactly this reason.
    """
    if not def_text:
        return []
    text = _TRAILING_PUNCT_RE.sub("", def_text.strip())
    if not text or "。" in text or "." in text:
        return []

    glosses = []
    for part in _GLOSS_SPLIT_RE.split(text):
        part = part.strip()
        if not part or part == headword:
            continue
        if len(part) > max_len:
            continue
        if any(ch in _DISQUALIFYING_CHARS for ch in part):
            continue
        glosses.append(part)
    return glosses


class UnionFind:
    """Groups headwords that are connected via a curated synonym/cross-reference
    signal (Cantonese sim:/# reference, Taiwanese synonyms field) so that,
    e.g., searching "抽菸" also surfaces an entry that's only linked to it
    through a shared synonym like "吸煙", not just entries that directly
    gloss to "抽菸" themselves. Deliberately NOT fed from generic short
    glosses (extract_glosses' output) — those are common enough that pooling
    them transitively would merge lots of unrelated words through overly
    generic hub terms.
    """

    def __init__(self):
        self._parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self._parent.setdefault(x, x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb


def parse_bracketed_example(raw: str):
    """Parses g0v moedict example markup.

    Taiwanese Hokkien: ￹original￺romanization￻translation
    Hakka:              ￹original￻translation   (no romanization segment)

    Returns (original_text, translation_zh_or_None).
    """
    text = raw
    translation = None
    if "￻" in text:
        text, translation = text.split("￻", 1)
        translation = translation.strip() or None
    if "￺" in text:
        text = text.split("￺", 1)[0]
    text = text.replace("￹", "").strip()
    return text, translation
