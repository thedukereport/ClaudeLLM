#!/usr/bin/env python3
"""
build_cuneiform.py — build cuneiform.sqlite for the cuneiform-chronicles MCP.

Scope: the openly-licensed CUNEIFORM ROYAL INSCRIPTIONS & HISTORIOGRAPHIC texts
from the CDLI bulk data dump — the primary Assyrian, Babylonian (and earlier
Sumerian/Akkadian) sources that carry regnal, campaign and synchronism data:
royal/monumental inscriptions, plus the open chronicle / king-list / eponym /
historical texts that appear in the dump.

Why not "the Babylonian Chronicle series" as such: the ancient chronicle TEXTS
are public domain, but their modern critical EDITIONS (Grayson, ABC; Glassner)
are under copyright and are on the project's do-not-install list. CDLI's open
ATF dump therefore carries the royal inscriptions richly and the chronicle
series only where an open transliteration exists. This corpus ingests what is
genuinely re-usable and labels its scope honestly.

Source & licence (CDLI Terms of Use, https://cdli.earth/terms-of-use):
  "Text in the pages of CDLI may be freely copied, aggregated and re-used
   according to common and fair academic practice; we request ... that mention
   be made of the source ... with reference to CDLI and its web address."
  (Only transliterations/translations are re-used here — NOT the copyrighted
   photographs or line art.)

Inputs (place next to this script; both are git-LFS objects in cdli-gh/data):
    cdliatf_unblocked.atf   ~83 MB   plain-text ATF transliterations
    cdli_cat.csv            ~148 MB  catalogue (genre, period, language, ...)

  Get them:
    git clone https://github.com/cdli-gh/data && cd data && git lfs fetch && git lfs checkout
  then copy cdliatf_unblocked.atf and cdli_cat.csv beside this script.

SQLite cannot be written on a network mount — build in /tmp, then cp the .sqlite
next to this script. Stdlib only.

    python3 build_cuneiform.py
"""

import csv
import os
import re
import sqlite3
import sys
from pathlib import Path

csv.field_size_limit(10 ** 9)

HERE = Path(__file__).resolve().parent
ATF = HERE / "cdliatf_unblocked.atf"
CAT = HERE / "cdli_cat.csv"
DB = HERE / "cuneiform.sqlite"

ATTRIBUTION = ("Cuneiform Digital Library Initiative (CDLI), transliteration re-used "
               "under CDLI Terms of Use (free re-use with attribution) — cdli.earth")

# historiographic scope
GENRES = {"royal/monumental", "royal/monumental ?", "royal/votive",
          "historical", "royal/monumental; literary"}
KEYWORDS = ("chronicle", "king list", "kinglist", "eponym", "date list",
            "historical", "astronomical diary", "astronomical diaries")

LINE_RE = re.compile(r"^[0-9]+['′\.]*\.?\s*(.*)$")


def parse_atf(path):
    """Yield (pnum, designation, text) per &P record. Keeps transliteration
    lines and #tr.en: translations; drops structural/metadata/composite lines."""
    texts = {}
    desig = {}
    cur = None
    buf = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("&P"):
                if cur and buf:
                    texts[cur] = " ".join(buf)
                head = line[1:].split("=", 1)
                cur = head[0].strip()
                desig[cur] = head[1].strip() if len(head) > 1 else ""
                buf = []
                continue
            if cur is None or not line.strip():
                continue
            c = line[0]
            if c in "#@$>":
                if line.startswith("#tr.en:"):
                    buf.append(line.split(":", 1)[1].strip())
                continue
            m = LINE_RE.match(line)
            buf.append(m.group(1) if m else line)
    if cur and buf:
        texts[cur] = " ".join(buf)
    return texts, desig


def norm_p(p):
    p = (p or "").strip()
    if p.startswith("P"):
        return p
    return "P" + p.zfill(6) if p.isdigit() else p


def build():
    if not ATF.exists() or not CAT.exists():
        sys.exit(f"Missing input(s). Expected:\n  {ATF}\n  {CAT}\n"
                 "See the module docstring for the git-lfs download steps.")
    print("parsing ATF …", flush=True)
    texts, desig = parse_atf(ATF)
    print(f"  {len(texts):,} texts with transliteration", flush=True)

    if DB.exists():
        DB.unlink()
    db = sqlite3.connect(DB)
    db.execute("CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)")
    db.execute("INSERT INTO meta VALUES('attribution',?)", (ATTRIBUTION,))
    db.execute("INSERT INTO meta VALUES('source','CDLI bulk data dump (cdli-gh/data)')")
    db.execute("INSERT INTO meta VALUES('license','CDLI Terms of Use — free re-use of text with attribution')")
    db.execute("CREATE TABLE docs(id INTEGER PRIMARY KEY, pnum TEXT UNIQUE, designation TEXT, "
               "genre TEXT, subgenre TEXT, period TEXT, provenience TEXT, language TEXT, text TEXT)")
    db.execute("CREATE VIRTUAL TABLE docs_fts USING fts5("
               "text, designation, pnum UNINDEXED, genre UNINDEXED, period UNINDEXED, "
               "content='docs', content_rowid='id', "
               "tokenize='unicode61 remove_diacritics 2')")

    rid = 0
    kept = 0
    with open(CAT, encoding="utf-8", errors="ignore") as f:
        r = csv.reader(f)
        hdr = next(r)
        col = {name: hdr.index(name) for name in
               ("id_text", "genre", "subgenre", "period", "provenience", "language", "designation")}
        for row in r:
            if len(row) <= max(col.values()):
                continue
            g = (row[col["genre"]] or "").strip()
            s = (row[col["subgenre"]] or "").strip()
            blob = (g + " " + s).lower()
            if not (g.lower() in GENRES or any(k in blob for k in KEYWORDS)):
                continue
            pn = norm_p(row[col["id_text"]])
            txt = texts.get(pn, "")
            if len(txt) < 30:
                continue
            rid += 1
            kept += 1
            db.execute("INSERT INTO docs VALUES(?,?,?,?,?,?,?,?,?)",
                       (rid, pn,
                        (row[col["designation"]] or desig.get(pn, "")).strip(),
                        g, s,
                        (row[col["period"]] or "").strip(),
                        (row[col["provenience"]] or "").strip(),
                        (row[col["language"]] or "").strip(),
                        txt))
    db.execute("INSERT INTO docs_fts(rowid, text, designation, pnum, genre, period) "
               "SELECT id, text, designation, pnum, genre, period FROM docs")
    db.execute("CREATE INDEX idx_period ON docs(period)")
    db.execute("CREATE INDEX idx_genre ON docs(genre)")
    db.commit()
    print(f"cuneiform.sqlite: {kept:,} texts")
    top = db.execute("SELECT period, count(*) c FROM docs GROUP BY period ORDER BY c DESC LIMIT 8").fetchall()
    for p, c in top:
        print(f"  {c:6}  {p}")


if __name__ == "__main__":
    build()
