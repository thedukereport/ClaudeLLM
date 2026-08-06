#!/usr/bin/env python3
"""
build_ethiopian.py — add the Ethiopian (Tewahedo) canon to scriptures.sqlite.

Source: LPettay/ethiopian-bible (GitHub) — 36 books, verse-level, with:
  * Ge'ez text from Beta Masaheft (Universität Hamburg), CC BY-SA 4.0
  * word-by-word transliteration (derived from the Ge'ez → CC BY-SA 4.0)
  * English — R.H. Charles (Enoch, Jubilees), Brenton LXX (1851) and KJV (1611),
    all public domain. Books with two traditions store BOTH (en = LXX, en-kjv = KJV).

Inserts one corpus, `ethiopian`, into the existing `docs` table (same schema as
the other corpora) and rebuilds the FTS index. Idempotent — re-running replaces
the ethiopian rows. Stdlib + git only.

    python3 build_ethiopian.py
"""

import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "scriptures.sqlite"
REPO = HERE / "ethiopian-bible"
DATA = REPO / "public" / "data"

LIC_GEEZ = "CC BY-SA 4.0 (Beta Masaheft)"
LIC_PD = "Public domain"


def ensure_repo():
    if DATA.is_dir():
        return
    print("Cloning LPettay/ethiopian-bible ...", flush=True)
    if REPO.exists():
        subprocess.run(["rm", "-rf", str(REPO)], check=False)
    subprocess.run(["git", "clone", "--depth", "1",
                    "https://github.com/LPettay/ethiopian-bible.git", str(REPO)],
                   check=True)
    if not DATA.is_dir():
        sys.exit("ERROR: clone succeeded but public/data is missing.")


def rows():
    """Yield (book, ref, lang, heading, body, license) for every verse."""
    books = json.loads((DATA / "books.json").read_text())
    meta = {b["abbrev"]: b for b in books}
    for abbrev, b in meta.items():
        name = b.get("name", abbrev)
        section = b.get("section", "")
        cdir = DATA / "chapters" / abbrev
        if not cdir.is_dir():
            continue
        for cf in sorted(cdir.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0):
            try:
                ch = json.loads(cf.read_text())
            except Exception:
                continue
            cnum = ch.get("chapter", cf.stem)
            for v in ch.get("verses", []):
                num = v.get("num")
                ref = f"{name} {cnum}:{num}"
                geez = (v.get("geez") or "").strip()
                if geez:
                    yield (name, ref, "gez", section, geez, LIC_GEEZ)
                words = v.get("words") or []
                translit = " ".join(w.get("t", "") for w in words if w.get("t")).strip()
                if translit:
                    yield (name, ref, "translit", section, translit, LIC_GEEZ)
                # English: single 'translation' (Charles) OR dual 'translations'
                prim = (v.get("translation") or "").strip()
                tr = v.get("translations") or {}
                if prim:
                    yield (name, ref, "en", section, prim, LIC_PD)
                else:
                    if tr.get("lxx", "").strip():
                        yield (name, ref, "en", section, tr["lxx"].strip(), LIC_PD)
                    if tr.get("kjv", "").strip():
                        yield (name, ref, "en-kjv", section, tr["kjv"].strip(), LIC_PD)


def build():
    ensure_repo()
    if not DB.exists():
        sys.exit(f"ERROR: {DB.name} not found — run build_scriptures.py first.")
    db = sqlite3.connect(DB)
    db.execute("DELETE FROM docs WHERE corpus='ethiopian'")
    batch, n = [], 0
    for book, ref, lang, heading, body, lic in rows():
        batch.append(("ethiopian", book, ref, lang, heading, body, lic))
        n += 1
        if len(batch) >= 4000:
            db.executemany("INSERT INTO docs(corpus,book,ref,lang,heading,body,license) "
                           "VALUES(?,?,?,?,?,?,?)", batch)
            batch = []
    if batch:
        db.executemany("INSERT INTO docs(corpus,book,ref,lang,heading,body,license) "
                       "VALUES(?,?,?,?,?,?,?)", batch)
    # rebuild the external-content FTS so the new rows are searchable
    db.execute("INSERT INTO docs_fts(docs_fts) VALUES('rebuild')")
    db.commit()
    refs = db.execute("SELECT COUNT(DISTINCT ref) FROM docs WHERE corpus='ethiopian'").fetchone()[0]
    langs = db.execute("SELECT lang, COUNT(*) FROM docs WHERE corpus='ethiopian' GROUP BY lang").fetchall()
    bks = db.execute("SELECT COUNT(DISTINCT book) FROM docs WHERE corpus='ethiopian'").fetchone()[0]
    print(f"ethiopian corpus: {n:,} rows, {refs:,} verses, {bks} books")
    print("  by language:", dict(langs))


if __name__ == "__main__":
    build()
