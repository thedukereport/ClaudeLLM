#!/usr/bin/env python3
"""
build_lewis_short.py — build lewis_short.sqlite for the Latin MCP server's
`lewis_short` dictionary tool.

Source: Lewis & Short, 'A Latin Dictionary' (1879), TEI XML from the Perseus
lexica repo (github.com/PerseusDL/lexica), CC BY-SA 4.0.

Downloads lat.ls.xml if it isn't already here, then parses every <entryFree>
into:  entries(id, key, headword, norm, n, text)  + FTS5(text).
The 'norm' column folds diacritics, lowercases, maps j→i and v→u and strips to
a–z, so 'Virtūs' / 'uirtus' / 'virtus' all resolve to one key.

Stdlib only. ~51,600 entries, ~46 MB, a few seconds.

    python3 build_lewis_short.py
"""

import os
import re
import sqlite3
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "lat.ls.xml"
DB = HERE / "lewis_short.sqlite"
URL = ("https://raw.githubusercontent.com/PerseusDL/lexica/master/"
       "CTS_XML_TEI/perseus/pdllex/lat/ls/lat.ls.perseus-eng1.xml")


def st(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def norm(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("j", "i").replace("v", "u")
    return re.sub(r"[^a-z]", "", s)


def inner(el):
    parts = [el.text or ""]
    for c in el:
        parts.append(inner(c))
        parts.append(c.tail or "")
    return "".join(parts)


def build():
    if not SRC.exists():
        print(f"Downloading Lewis & Short TEI → {SRC.name} ...", flush=True)
        urllib.request.urlretrieve(URL, SRC)
    if DB.exists():
        DB.unlink()
    db = sqlite3.connect(DB)
    db.execute("CREATE TABLE entries(id INTEGER PRIMARY KEY, key TEXT, "
               "headword TEXT, norm TEXT, n TEXT, text TEXT)")
    rows, n = [], 0
    for _ev, el in ET.iterparse(str(SRC), events=("end",)):
        if st(el.tag) != "entryFree":
            continue
        orth = None
        for c in el:
            if st(c.tag) == "orth":
                orth = (c.text or "").strip()
                break
        key = el.get("key") or ""
        head = orth or re.sub(r"\d+$", "", key)
        txt = re.sub(r"\s+", " ", inner(el)).strip()
        rows.append((key, head, norm(head) or norm(key), el.get("n") or "", txt))
        n += 1
        el.clear()
        if len(rows) >= 2000:
            db.executemany("INSERT INTO entries(key,headword,norm,n,text) "
                           "VALUES(?,?,?,?,?)", rows)
            rows = []
    if rows:
        db.executemany("INSERT INTO entries(key,headword,norm,n,text) "
                       "VALUES(?,?,?,?,?)", rows)
    db.execute("CREATE INDEX idx_norm ON entries(norm)")
    db.execute("CREATE VIRTUAL TABLE fts USING fts5(text, content='entries', "
               "content_rowid='id')")
    db.execute("INSERT INTO fts(rowid, text) SELECT id, text FROM entries")
    db.commit()
    print(f"lewis_short.sqlite built: {n:,} entries")


if __name__ == "__main__":
    build()
