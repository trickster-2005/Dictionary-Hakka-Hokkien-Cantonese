"""Shared helpers for the g0v moedict-derived parsers (parse_nan.py, parse_hak.py)."""
import re

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
    """
    if not def_text:
        return []
    text = _TRAILING_PUNCT_RE.sub("", def_text.strip())
    if not text:
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
