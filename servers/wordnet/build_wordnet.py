#!/usr/bin/env python3
"""
build_wordnet.py — build wordnet.sqlite for the WordNet MCP server.

Source: Open English WordNet (the maintained successor to Princeton WordNet),
WN-LMF XML, licensed CC BY 4.0. https://github.com/globalwordnet/english-wordnet

Downloads the release .xml.gz if it isn't here, then parses it (stdlib only,
streaming) into wordnet.sqlite:

  synsets(id, pos, definition, examples)
  words(lemma, lemma_lc, pos, synset_id, sense_id)     -- lemma ↔ synset
  srel(source, reltype, target)                        -- synset → synset (hypernym…)
  wrel(source_sense, reltype, target_sense)            -- sense → sense (antonym…)
  syn_fts(definition)                                  -- FTS5 over glosses

~107k synsets, ~305k senses, ~120k lemmas. A minute or two.

    python3 build_wordnet.py
"""

import gzip
import os
import re
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
GZ = HERE / "english-wordnet-2025.xml.gz"
DB = HERE / "wordnet.sqlite"
URL = ("https://github.com/globalwordnet/english-wordnet/releases/download/"
       "2025-edition/english-wordnet-2025.xml.gz")

POS = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}


def tag(e):
    return e.tag.split("}", 1)[1] if "}" in e.tag else e.tag


def ensure_src():
    if GZ.exists() or (HERE / "english-wordnet-2025.xml").exists():
        return
    print(f"Downloading Open English WordNet → {GZ.name} (~11 MB) ...", flush=True)
    urllib.request.urlretrieve(URL, GZ)


def open_xml():
    plain = HERE / "english-wordnet-2025.xml"
    if plain.exists():
        return open(plain, "rb")
    return gzip.open(GZ, "rb")


def build(db_path=DB, src=None):
    ensure_src()
    if os.path.exists(db_path):
        os.remove(db_path)
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE synsets(id TEXT PRIMARY KEY, pos TEXT, definition TEXT, examples TEXT)")
    db.execute("CREATE TABLE words(lemma TEXT, lemma_lc TEXT, pos TEXT, synset_id TEXT, sense_id TEXT)")
    db.execute("CREATE TABLE srel(source TEXT, reltype TEXT, target TEXT)")
    db.execute("CREATE TABLE wrel(source_sense TEXT, reltype TEXT, target_sense TEXT)")

    words, syns, sr, wr = [], [], [], []
    fh = src or open_xml()
    for _ev, el in ET.iterparse(fh, events=("end",)):
        t = tag(el)
        if t == "LexicalEntry":
            lemma = pos = None
            for c in el:
                if tag(c) == "Lemma":
                    lemma = c.get("writtenForm"); pos = c.get("partOfSpeech")
            for c in el:
                if tag(c) == "Sense":
                    sid = c.get("id"); syn = c.get("synset")
                    if lemma and syn:
                        words.append((lemma, lemma.lower(), pos, syn, sid))
                    for gc in c:
                        if tag(gc) == "SenseRelation":
                            wr.append((sid, gc.get("relType"), gc.get("target")))
            el.clear()
        elif t == "Synset":
            sid = el.get("id"); pos = el.get("partOfSpeech")
            defi = ""; ex = []
            for c in el:
                tc = tag(c)
                if tc == "Definition" and not defi:
                    defi = (c.text or "").strip()
                elif tc == "Example":
                    ex.append((c.text or "").strip())
                elif tc == "SynsetRelation":
                    sr.append((sid, c.get("relType"), c.get("target")))
            syns.append((sid, pos, defi, " | ".join(ex)))
            el.clear()
        if len(words) >= 5000:
            db.executemany("INSERT INTO words VALUES(?,?,?,?,?)", words); words = []
        if len(syns) >= 5000:
            db.executemany("INSERT INTO synsets VALUES(?,?,?,?)", syns); syns = []
        if len(sr) >= 8000:
            db.executemany("INSERT INTO srel VALUES(?,?,?)", sr); sr = []
        if len(wr) >= 8000:
            db.executemany("INSERT INTO wrel VALUES(?,?,?)", wr); wr = []
    if words: db.executemany("INSERT INTO words VALUES(?,?,?,?,?)", words)
    if syns: db.executemany("INSERT INTO synsets VALUES(?,?,?,?)", syns)
    if sr: db.executemany("INSERT INTO srel VALUES(?,?,?)", sr)
    if wr: db.executemany("INSERT INTO wrel VALUES(?,?,?)", wr)

    db.execute("CREATE INDEX idx_word ON words(lemma_lc)")
    db.execute("CREATE INDEX idx_word_syn ON words(synset_id)")
    db.execute("CREATE INDEX idx_word_sense ON words(sense_id)")
    db.execute("CREATE INDEX idx_srel ON srel(source, reltype)")
    db.execute("CREATE INDEX idx_wrel ON wrel(source_sense, reltype)")
    db.execute("CREATE VIRTUAL TABLE syn_fts USING fts5(definition, content='synsets', "
               "content_rowid='rowid', tokenize='unicode61 remove_diacritics 2')")
    db.execute("INSERT INTO syn_fts(rowid, definition) SELECT rowid, definition FROM synsets")
    db.commit()
    ns = db.execute("SELECT COUNT(*) FROM synsets").fetchone()[0]
    nw = db.execute("SELECT COUNT(DISTINCT lemma_lc) FROM words").fetchone()[0]
    print(f"wordnet.sqlite: {ns:,} synsets, {nw:,} distinct words, "
          f"{db.execute('SELECT COUNT(*) FROM srel').fetchone()[0]:,} synset-relations, "
          f"{db.execute('SELECT COUNT(*) FROM wrel').fetchone()[0]:,} sense-relations")


if __name__ == "__main__":
    build()
