#!/usr/bin/env python3
"""
build_wiktionary.py — build wiktionary.sqlite for the Wiktionary MCP server.

Source: kaikki.org machine-readable dictionary — Tatu Ylonen's wiktextract
extract of the ENGLISH edition of Wiktionary (enwiktionary). It covers HUNDREDS
of languages (Sumerian, Akkadian, Hebrew, Ancient Greek, Latin, English, ...)
with glosses and etymologies in English. CC BY-SA 4.0 (Wiktionary) / wiktextract.

    https://kaikki.org/dictionary/rawdata.html
    file: raw-wiktextract-data.jsonl.gz  (~2.8 GB compressed, ~24 GB raw)

This script STREAMS the .gz line by line (it never unpacks the 24 GB to disk),
parses each JSON object, prunes the bulky/noise fields, and loads the rest into
wiktionary.sqlite:

  entries(id, word, word_lc, lang, lang_code, pos, etymology, data)
      -- one row per (word, language, part-of-speech); `data` is a pruned JSON
         blob holding senses, sounds/IPA, forms, translations, descendants,
         derived, related, synonyms, antonyms, hypernyms, hyphenation.
  gloss_fts(gloss, word, lang_code, entry_id)   -- FTS5 over every sense gloss

Stdlib only. Runs on any Python 3.8+.

Typical use (downloads if the .gz isn't already here, then builds):
    python3 build_wiktionary.py

Build from a file you already downloaded:
    python3 build_wiktionary.py --src /path/to/raw-wiktextract-data.jsonl.gz

Build a tiny DB from a sample (for testing the server):
    python3 build_wiktionary.py --src sample.jsonl --db test.sqlite

Download is resumable: re-run and it continues the partial .gz via HTTP Range.
"""

import argparse
import gzip
import io
import json
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
GZ = HERE / "raw-wiktextract-data.jsonl.gz"
DB = HERE / "wiktionary.sqlite"
URL = "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz"

# Per-list caps so a single pathological entry (huge declension/translation
# tables) can't bloat the DB. Generous — real entries rarely approach these.
CAP = {"senses": 60, "sounds": 40, "forms": 80, "translations": 400,
       "derived": 500, "descendants": 500, "related": 300,
       "synonyms": 200, "antonyms": 200, "hypernyms": 200, "holonyms": 100,
       "meronyms": 100, "hyponyms": 300}

# Fields dropped from the stored blob (large and not useful for lookup/etymology).
DROP = {"categories", "wikipedia", "wikidata", "senses_categories",
        "head_templates", "inflection_templates", "etymology_templates",
        "etymology_number", "redirects", "hyphenations_list"}


def ensure_src():
    """Download the .gz if it isn't already present, resuming a partial file."""
    if GZ.exists():
        return
    part = GZ.with_suffix(GZ.suffix + ".part")
    existing = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(URL)
    if existing:
        req.add_header("Range", f"bytes={existing}-")
        print(f"Resuming download at {existing/1e6:.0f} MB ...", flush=True)
    else:
        print(f"Downloading {URL}\n  → {part.name} (~2.8 GB) ...", flush=True)
    with urllib.request.urlopen(req) as r:
        total = int(r.headers.get("Content-Length", 0)) + existing
        mode = "ab" if existing else "wb"
        done = existing
        with open(part, mode) as out:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if total:
                    pct = 100 * done / total
                    print(f"\r  {done/1e6:8.0f} / {total/1e6:.0f} MB  ({pct:4.1f}%)",
                          end="", flush=True)
    print()
    part.rename(GZ)


def open_src(src):
    """Return a text file handle over the JSONL, whether .gz or plain."""
    p = Path(src)
    if p.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(p, "rb"), encoding="utf-8")
    return open(p, "r", encoding="utf-8")


def prune(obj):
    """Shrink one wiktextract entry to the fields we store in `data`."""
    out = {}
    for k, v in obj.items():
        if k in DROP or k in ("word", "lang", "lang_code", "pos", "etymology_text"):
            continue
        if isinstance(v, list) and k in CAP:
            v = v[:CAP[k]]
        out[k] = v
    return out


def iter_glosses(obj):
    """Yield every gloss string from an entry's senses."""
    for s in obj.get("senses", []) or []:
        for g in (s.get("glosses") or s.get("raw_glosses") or []):
            if g:
                yield g


def load_jsonl(fh, db, progress_every=200000):
    """Load an open JSONL text handle into an open sqlite connection."""
    db.executescript("""
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE entries(
            id INTEGER PRIMARY KEY,
            word TEXT, word_lc TEXT, lang TEXT, lang_code TEXT,
            pos TEXT, etymology TEXT, data TEXT);
        CREATE VIRTUAL TABLE gloss_fts USING fts5(
            gloss, word, lang_code, entry_id UNINDEXED,
            tokenize='unicode61 remove_diacritics 2');
    """)
    rows, fts = [], []
    n = 0
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        word = obj.get("word")
        if not word:
            continue
        n += 1
        eid = n
        rows.append((eid, word, word.lower(), obj.get("lang"),
                     obj.get("lang_code"), obj.get("pos"),
                     obj.get("etymology_text"),
                     json.dumps(prune(obj), ensure_ascii=False)))
        for g in iter_glosses(obj):
            fts.append((g, word, obj.get("lang_code"), eid))
        if len(rows) >= 5000:
            db.executemany("INSERT INTO entries VALUES(?,?,?,?,?,?,?,?)", rows)
            rows = []
        if len(fts) >= 10000:
            db.executemany("INSERT INTO gloss_fts VALUES(?,?,?,?)", fts)
            fts = []
        if progress_every and n % progress_every == 0:
            print(f"\r  {n:,} entries ...", end="", flush=True)
    if rows:
        db.executemany("INSERT INTO entries VALUES(?,?,?,?,?,?,?,?)", rows)
    if fts:
        db.executemany("INSERT INTO gloss_fts VALUES(?,?,?,?)", fts)
    print(f"\r  {n:,} entries loaded.          ", flush=True)
    return n


def build(db_path=DB, src=None):
    if src is None:
        ensure_src()
        src = GZ
    if os.path.exists(db_path):
        os.remove(db_path)
    db = sqlite3.connect(db_path)
    fh = open_src(src)
    try:
        n = load_jsonl(fh, db)
    finally:
        fh.close()
    print("Indexing ...", flush=True)
    db.execute("CREATE INDEX idx_word ON entries(word_lc)")
    db.execute("CREATE INDEX idx_word_lang ON entries(word_lc, lang_code)")
    db.execute("CREATE INDEX idx_lang ON entries(lang_code)")
    db.commit()
    langs = db.execute("SELECT COUNT(DISTINCT lang_code) FROM entries").fetchone()[0]
    words = db.execute("SELECT COUNT(DISTINCT word_lc) FROM entries").fetchone()[0]
    glosses = db.execute("SELECT COUNT(*) FROM gloss_fts").fetchone()[0]
    print(f"wiktionary.sqlite: {n:,} entries, {words:,} distinct headwords, "
          f"{langs:,} languages, {glosses:,} glosses indexed.")
    db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build wiktionary.sqlite from kaikki wiktextract data.")
    ap.add_argument("--src", help="Path to raw-wiktextract-data.jsonl[.gz] (default: download it here)")
    ap.add_argument("--db", default=str(DB), help="Output sqlite path (default: wiktionary.sqlite)")
    args = ap.parse_args()
    build(db_path=args.db, src=args.src)
