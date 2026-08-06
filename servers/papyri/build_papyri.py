#!/usr/bin/env python3
"""
build_papyri.py — build papyri.sqlite for the DDbDP MCP server.

Source: the Duke Databank of Documentary Papyri (DDbDP), EpiDoc XML, from the
papyri.info data repo (github.com/papyri/idp.data, directory DDbDP). CC BY 3.0.

What it does:
  1. If ./idp.data/DDbDP isn't present, sparse-clones just that directory
     (~500 MB, no full-repo history) using git.
  2. Parses every EpiDoc file → papyri.sqlite:
       docs(id, tm, hybrid, citation, langs, text)  + FTS5(citation, text)
     with an accent-insensitive Greek tokenizer.

Stdlib + git only (no Python packages). Resumable: re-running rebuilds the DB
from whatever is already cloned. Takes ~15 s to parse once cloned.

    python3 build_papyri.py
"""

import os
import re
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE / "idp.data"
DDB = REPO / "DDbDP"
DB = HERE / "papyri.sqlite"
NS = "{http://www.tei-c.org/ns/1.0}"
XMLID = "{http://www.w3.org/XML/1998/namespace}id"


def ensure_data():
    """Sparse-clone just the DDbDP directory if it isn't here yet."""
    if DDB.is_dir():
        return
    print("DDbDP not found — sparse-cloning from papyri/idp.data ...", flush=True)
    if REPO.exists():
        subprocess.run(["rm", "-rf", str(REPO)], check=False)
    subprocess.run(["git", "clone", "--depth", "1", "--no-checkout",
                    "https://github.com/papyri/idp.data.git", str(REPO)], check=True)
    subprocess.run(["git", "-C", str(REPO), "sparse-checkout", "init", "--cone"], check=True)
    subprocess.run(["git", "-C", str(REPO), "sparse-checkout", "set", "DDbDP"], check=True)
    subprocess.run(["git", "-C", str(REPO), "checkout"], check=True)
    if not DDB.is_dir():
        sys.exit("ERROR: clone succeeded but DDbDP/ is still missing.")


def edition_text(root):
    for div in root.iter(f"{NS}div"):
        if div.get("type") == "edition":
            return re.sub(r"\s+", " ", "".join(div.itertext())).strip()
    return ""


def build():
    ensure_data()
    if DB.exists():
        DB.unlink()
    db = sqlite3.connect(DB)
    db.execute("CREATE TABLE docs(id TEXT PRIMARY KEY, tm TEXT, hybrid TEXT, "
               "citation TEXT, langs TEXT, text TEXT)")
    db.execute("CREATE VIRTUAL TABLE fts USING fts5(citation, text, "
               "content='docs', content_rowid='rowid', "
               "tokenize=\"unicode61 remove_diacritics 2\")")
    files = list(DDB.rglob("*.xml"))
    rows, seen, t0 = [], 0, time.time()
    for fp in files:
        seen += 1
        try:
            root = ET.parse(fp).getroot()
        except Exception:
            continue
        xmlid = root.get(XMLID) or fp.stem
        tm = hybrid = None
        for idno in root.iter(f"{NS}idno"):
            ty = idno.get("type")
            if ty == "TM" and tm is None:
                tm = (idno.text or "").strip()
            elif ty == "ddb-hybrid" and hybrid is None:
                hybrid = (idno.text or "").strip()
        langs = ",".join(sorted({l.get("ident") for l in root.iter(f"{NS}language")
                                 if l.get("ident")}))
        txt = edition_text(root)
        if len(txt) < 3:            # skip reprint/redirect stubs with no text
            continue
        rows.append((xmlid, tm, hybrid, xmlid, langs, txt))
        if len(rows) >= 3000:
            db.executemany("INSERT OR IGNORE INTO docs VALUES(?,?,?,?,?,?)", rows)
            rows = []
    if rows:
        db.executemany("INSERT OR IGNORE INTO docs VALUES(?,?,?,?,?,?)", rows)
    db.execute("INSERT INTO fts(rowid, citation, text) SELECT rowid, citation, text FROM docs")
    db.execute("CREATE INDEX idx_tm ON docs(tm)")
    db.commit()
    tot = db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    print(f"papyri.sqlite built: {tot:,} documents "
          f"(scanned {seen:,} files) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    build()
