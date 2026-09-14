#!/usr/bin/env python3
"""
build_chronography.py — build chronography.sqlite for the ancient-synchronism
MCP server.

Public-domain primary sources of ancient chronography, downloaded from the
Internet Archive and segmented into a searchable FTS5 table:

  eusebius-latin        Eusebius, Chronici Canones — Jerome's Latin
                        (ed. J. K. Fotheringham, Oxford 1923)              [PD]
  eusebius-armenian-de  Eusebius, Chronik — Armenian version, German tr.
                        (J. Karst, GCS 20, Leipzig 1911)                  [PD]
  syncellus             George Syncellus, Ecloga Chronographica
                        (ed. Dindorf, CSHB, Bonn 1829) — preserves Manetho,
                        Berossus, Julius Africanus fragments              [PD]

Africanus (#4) is not a separate download: his Chronographiai survive only as
fragments embedded in Eusebius and Syncellus, so he is cross-searchable here
once those two are loaded.

Stdlib only. ~2,700 segments, ~6 MB, under a minute (after download).

    python3 build_chronography.py
"""

import os
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "chronography.sqlite"
AIA = "https://archive.org/download"

SOURCES = [
    dict(id="eusebius-latin", ia="eusebiipamphilic0000unse", lang="la",
         title="Chronici Canones (Chronicle)", author="Eusebius / Jerome",
         edition="ed. J. K. Fotheringham, Oxford 1923", license="Public domain",
         attribution="Eusebius, Chronici Canones, Jerome's Latin, ed. Fotheringham (Oxford, 1923) [public domain]",
         quality="good (clean Latin OCR)"),
    dict(id="eusebius-armenian-de", ia="chronikausdemarm00euse", lang="de",
         title="Chronik (Armenian version, German translation)", author="Eusebius / Josef Karst",
         edition="GCS 20, tr. J. Karst, Leipzig 1911", license="Public domain",
         attribution="Eusebius, Chronik (Armenian), German tr. J. Karst, GCS 20 (Leipzig, 1911) [public domain]",
         quality="good (German OCR)"),
    dict(id="syncellus", ia="georgiussyncell01goargoog", lang="grc+la",
         title="Ecloga Chronographica", author="George Syncellus",
         edition="ed. W. Dindorf, CSHB (Bonn, 1829)", license="Public domain",
         attribution=("George Syncellus, Ecloga Chronographica, ed. Dindorf, CSHB "
                      "(Bonn, 1829) [public domain]. Preserves fragments of Manetho, "
                      "Berossus, and Julius Africanus."),
         quality="mixed — 1829 scan; Latin apparatus clean, polytonic Greek OCR is rough"),
]


def fetch(s):
    dest = HERE / f"{s['id']}.txt"
    if dest.exists():
        return dest
    url = f"{AIA}/{s['ia']}/{s['ia']}_djvu.txt"
    print(f"  downloading {s['id']} …", flush=True)
    urllib.request.urlretrieve(url, dest)
    return dest


def segments(text, size=180):
    words = re.sub(r"[ \t]+", " ", text).split()
    for i in range(0, len(words), size):
        seg = " ".join(words[i:i + size]).strip()
        if len(seg) >= 40:
            yield seg


def build():
    if DB.exists():
        DB.unlink()
    db = sqlite3.connect(DB)
    db.execute("CREATE TABLE sources(id TEXT PRIMARY KEY, title TEXT, author TEXT, "
               "edition TEXT, lang TEXT, license TEXT, attribution TEXT, quality TEXT, segments INT)")
    db.execute("CREATE TABLE docs(id INTEGER PRIMARY KEY, source TEXT, seq INT, lang TEXT, text TEXT)")
    db.execute("CREATE VIRTUAL TABLE docs_fts USING fts5(text, source UNINDEXED, "
               "content='docs', content_rowid='id', tokenize='unicode61 remove_diacritics 2')")
    rid = 0
    for s in SOURCES:
        raw = open(fetch(s), encoding="utf-8", errors="ignore").read()
        n, batch = 0, []
        for seg in segments(raw):
            rid += 1; n += 1
            batch.append((rid, s["id"], n, s["lang"], seg))
            if len(batch) >= 2000:
                db.executemany("INSERT INTO docs(id,source,seq,lang,text) VALUES(?,?,?,?,?)", batch); batch = []
        if batch:
            db.executemany("INSERT INTO docs(id,source,seq,lang,text) VALUES(?,?,?,?,?)", batch)
        db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?)",
                   (s["id"], s["title"], s["author"], s["edition"], s["lang"],
                    s["license"], s["attribution"], s["quality"], n))
        print(f"  {s['id']:22} {n:6} segments")
    db.execute("INSERT INTO docs_fts(rowid,text,source) SELECT id,text,source FROM docs")
    db.execute("CREATE INDEX idx_src ON docs(source,seq)")
    db.commit()
    print(f"chronography.sqlite: {db.execute('SELECT count(*) FROM docs').fetchone()[0]:,} segments, "
          f"{len(SOURCES)} sources")


if __name__ == "__main__":
    build()
