"""Downloads the g0v-processed MOE Hakka dictionary source used by
parse_hak.py. Safe to re-run — skips files already present unless force=True.

parse_nan.py no longer has an entry here: it originally read g0v's
moedict-data-twblg JSON export, but that export is missing the entire
"臺華共同詞" category (~5,500 headwords with no separate definition, e.g.
"繁華") along with several other 詞目類型 categories — g0v's own processing
pipeline drops them. It now reads data/raw/kautian.ods directly, the same
multi-sheet export the official 教育部臺灣台語常用詞辭典 download page
offers — there's no stable auto-fetchable URL for it, so it has to be
placed in data/raw/ manually (like 粵典辭典資料.csv already is).
"""
import urllib.parse
import urllib.request
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"

SOURCES = {
    # The raw spreadsheet, not moedict-data-hakka's dict-hakka.json: it has
    # 對應國語/近義詞 columns (and plain-text 調值 pronunciation for all six
    # accents) that never made it into that repo's JSON conversion.
    "客語典文字資料.ods": (
        "https://raw.githubusercontent.com/g0v/moedict-data-hakka/master/ods/"
        + urllib.parse.quote("客語典文字資料.ods")
    ),
}


def fetch(force: bool = False):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in SOURCES.items():
        dest = RAW_DIR / filename
        if dest.exists() and not force:
            print(f"  skip {filename} (already present, {dest.stat().st_size:,} bytes)")
            continue
        print(f"  downloading {filename} ...")
        urllib.request.urlretrieve(url, dest)
        print(f"    saved {dest.stat().st_size:,} bytes")


if __name__ == "__main__":
    fetch(force=True)
