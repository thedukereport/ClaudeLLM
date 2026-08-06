#!/usr/bin/env python3
"""
Add word-level lexicons to scriptures.sqlite (additive — leaves `docs` untouched).

  bdb      Brown-Driver-Briggs Hebrew & Aramaic Lexicon   [public domain, 1906]
           source: openscriptures/HebrewLexicon
  jastrow  Dictionary of the Targumim, Talmud & Midrash    [public domain, 1903/26]
           source: BraydenKO/Jastrow-Klein-Dicts (Sefaria digitization)
  lane     Lane's Arabic-English Lexicon, keyed by the      [public domain, 1863-93]
           1,651 Qur'anic roots
           source: aliozdenisik/quran-arabic-roots-lane-lexicon

Creates table `lex` + FTS5 `lex_fts`. Stdlib only. Resumable (caches to
./sources_lex/). Run after build_scriptures.py has produced scriptures.sqlite.

  python3 build_lexicons.py
  python3 build_lexicons.py --only bdb,jastrow
"""
import os, re, sys, json, time, sqlite3, argparse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC  = HERE / "sources_lex"
DB   = HERE / "scriptures.sqlite"
UA   = {"User-Agent": "scriptures-build/1.0 (peter research corpus; peter@dukemedia.com)"}
SRC.mkdir(exist_ok=True)

RAW = "https://raw.githubusercontent.com"
BDB_URL = f"{RAW}/openscriptures/HebrewLexicon/master/BrownDriverBriggs.xml"
JAS_BASE = (f"{RAW}/BraydenKO/Jastrow-Klein-Dicts/master/Jastrow/data/00-Separate%20XML")
JAS_FILES = [
    "01-Jastrow-aleph.xml", "02-Jastrow-beth.xml", "03-Jastrow-gimel.xml",
    "04-Jastrow-daleth.xml", "05-Jastrow-he.xml", "06-Jastrow-vav.xml",
    "07-Jastrow-zayin.xml", "08-Jastrow-heth.xml", "09-Jastrow-teth.xml",
    "10-Jastrow-yod.xml", "11-Jastrow-kaf.xml", "12-Jastrow-lamed.xml",
    "13-Jastrow-mem.xml", "14-Jastrow-nun.xml", "15-Jastrow-samech.xml",
    "16-Jastrow-ayin.xml", "17-Jastrow-pe.xml", "18-Jastrow-tsade.xml",
    "19-Jastrow-qof.xml", "20-Jastrow-resh.xml", "21-Jastrow-shin.xml",
    "22-Jastrow-tav.xml",
]
LANE_URL = (f"{RAW}/aliozdenisik/quran-arabic-roots-lane-lexicon/main/"
            "quran_arabic_roots_lane_lexicon_2026-02-12.json")

PD_BDB = "Public domain (Brown-Driver-Briggs, 1906; digitization: openscriptures)"
PD_JAS = "Public domain (Jastrow, 1903/1926; digitization: Sefaria)"
PD_LANE = "Public domain (Lane's Lexicon, 1863-93; Qur'anic-root compilation)"

# diacritics: Hebrew points/cantillation 0591-05C7, Arabic harakat 064B-0652 + 0670, tatweel 0640
_STRIP = re.compile("[֑-ׇً-ْٰـ]")
_WS = re.compile(r"\s+")
def plain(s):
    return _STRIP.sub("", s or "").strip()
def norm(s):
    return _WS.sub(" ", (s or "").replace("\n", " ")).strip()

def cache(url, name):
    p = SRC / name
    if p.exists() and p.stat().st_size > 0:
        return p.read_bytes()
    for i in range(4):
        try:
            data = urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=45).read()
            p.write_bytes(data); return data
        except Exception as e:
            last = e; time.sleep(1.5 * (i + 1))
    raise last

def localname(tag):
    return tag.rsplit("}", 1)[-1]

def itertext_clean(el):
    return norm("".join(el.itertext()))

# ---------------------------------------------------------------- BDB
def load_bdb(rows):
    data = cache(BDB_URL, "bdb.xml")
    root = ET.fromstring(data)
    n = 0
    for entry in root.iter():
        if localname(entry.tag) != "entry":
            continue
        # first <w> child = headword
        hw = None
        for ch in entry:
            if localname(ch.tag) == "w":
                hw = norm("".join(ch.itertext())); break
        if not hw:
            continue
        definition = itertext_clean(entry)
        # drop the leading headword duplicate if present
        if definition.startswith(hw):
            definition = definition[len(hw):].strip(" ,;")
        if not definition:
            continue
        rows.append(("bdb", "he", hw, plain(hw), "", definition, PD_BDB))
        n += 1
    return n

# ---------------------------------------------------------------- Jastrow
def load_jastrow(rows):
    n = 0
    for i, fn in enumerate(JAS_FILES, 1):
        try:
            data = cache(f"{JAS_BASE}/{fn}", f"jastrow_{i:02d}.xml")
        except Exception as e:
            print(f"    ! {fn}: {e}", flush=True); continue
        try:
            root = ET.fromstring(data)
        except ET.ParseError as e:
            print(f"    ! parse {fn}: {e}", flush=True); continue
        for entry in root.iter("entry"):
            heads = [norm("".join(h.itertext())).strip(" ,")
                     for h in entry.findall("head-word")]
            heads = [h for h in heads if h]
            if not heads:
                continue
            defs = []
            for sense in entry.iter("sense"):
                d = entry_sense_text(sense)
                if d:
                    defs.append(d)
            definition = " / ".join(defs) if defs else itertext_clean(entry)
            if not definition:
                continue
            primary = heads[0]
            allhw = "; ".join(heads)
            rows.append(("jastrow", "he", allhw, plain(primary), "",
                         definition, PD_JAS))
            n += 1
        if i % 6 == 0:
            print(f"    jastrow: {i}/22 files", flush=True)
    return n

def entry_sense_text(sense):
    parts = []
    for child in sense:
        ln = localname(child.tag)
        if ln in ("definition", "notes"):
            t = norm("".join(child.itertext()))
            if t:
                parts.append(t)
    return " ".join(parts).strip(" ,;")

# ---------------------------------------------------------------- Lane
def load_lane(rows):
    data = json.loads(cache(LANE_URL, "lane_quran_roots.json"))
    n = 0
    for r in data.get("roots", []):
        root_ar = r.get("root") or ""
        definition = (r.get("definition_en") or r.get("summary_en")
                      or r.get("summary_tr") or "").strip()
        if not root_ar or not definition:
            continue
        bw = r.get("root_buckwalter") or ""
        rows.append(("lane", "ar", root_ar, plain(root_ar), bw,
                     norm(definition), PD_LANE))
        n += 1
    return n

# ---------------------------------------------------------------- DB
def write_lex(rows):
    if not DB.exists():
        sys.exit(f"scriptures.sqlite not found at {DB}. Run build_scriptures.py first.")
    con = sqlite3.connect(DB)
    con.executescript("""
      PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      DROP TABLE IF EXISTS lex_fts;
      DROP TABLE IF EXISTS lex;
      CREATE TABLE lex(
        id INTEGER PRIMARY KEY, lexicon TEXT, lang TEXT,
        headword TEXT, headword_plain TEXT, root TEXT,
        definition TEXT, license TEXT);
      CREATE INDEX idx_lex_hw   ON lex(headword_plain);
      CREATE INDEX idx_lex_root ON lex(root);
      CREATE VIRTUAL TABLE lex_fts USING fts5(
        headword, definition, lexicon UNINDEXED,
        content='lex', content_rowid='id',
        tokenize='unicode61 remove_diacritics 2');
    """)
    con.executemany(
        "INSERT INTO lex(lexicon,lang,headword,headword_plain,root,definition,license) "
        "VALUES(?,?,?,?,?,?,?)", rows)
    con.execute("INSERT INTO lex_fts(lex_fts) VALUES('rebuild')")
    con.commit()
    stats = con.execute(
        "SELECT lexicon, COUNT(*) FROM lex GROUP BY lexicon ORDER BY lexicon").fetchall()
    con.close()
    return stats

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="bdb,jastrow,lane")
    args = ap.parse_args()
    want = set(x.strip() for x in args.only.split(",") if x.strip())
    rows = []
    if "bdb" in want:
        print("BDB ...", flush=True);     print("  entries:", load_bdb(rows), flush=True)
    if "jastrow" in want:
        print("Jastrow ...", flush=True); print("  entries:", load_jastrow(rows), flush=True)
    if "lane" in want:
        print("Lane ...", flush=True);    print("  roots:", load_lane(rows), flush=True)
    print(f"\nWriting {len(rows):,} lexicon entries into scriptures.sqlite ...", flush=True)
    for lx, c in write_lex(rows):
        print(f"  {lx:8} {c:>7,}")

if __name__ == "__main__":
    main()
