"""Downloads the g0v-processed MOE dictionary JSON dumps used by parse_nan.py
and parse_hak.py. Safe to re-run — skips files already present unless force=True.
"""
import urllib.request
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"

SOURCES = {
    "dict-twblg.json": "https://raw.githubusercontent.com/g0v/moedict-data-twblg/master/dict-twblg.json",
    "dict-hakka.json": "https://raw.githubusercontent.com/g0v/moedict-data-hakka/master/dict-hakka.json",
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
