#!/usr/bin/env python3
"""
Build a local searchable Pleiades gazetteer (ancient places) as SQLite + FTS5.

Pleiades (https://pleiades.stoa.org) is a community gazetteer of the ancient
world — ~42k places with coordinates, time periods, feature types, and all
attested + transliterated names. Licensed CC-BY.

Downloads the official CC-BY CSV dumps (places + names), joins every place to
its name variants, and writes pleiades.sqlite with an FTS5 index over
title + names + description — so a search for a modern title, an attested Greek
name, or a transliteration all find the place.

Stdlib only. Run on the Mac to refresh:
    python3 build_pleiades_corpus.py            # downloads latest dumps
    python3 build_pleiades_corpus.py --places places.csv --names names.csv
"""

import csv
import sys
import gzip
import sqlite3
import argparse
import urllib.request
from pathlib import Path

csv.field_size_limit(1 << 24)
BASE = "https://atlantides.org/downloads/pleiades/dumps/"
HERE = Path(__file__).resolve().parent


def load_csv(src, is_gz):
    if is_gz:
        with gzip.open(src, "rt", encoding="utf-8", newline="") as f:
            yield from csv.DictReader(f)
    else:
        with open(src, "rt", encoding="utf-8", newline="") as f:
            yield from csv.DictReader(f)


def fetch(name, dest):
    url = BASE + name
    print(f"  downloading {name} ...", flush=True)
    urllib.request.urlretrieve(url, dest)
    return dest


def build(places_src, names_src, out_path, places_gz=False, names_gz=False):
    # names grouped by place id
    print("Reading names ...", flush=True)
    names_by_pid = {}
    for r in load_csv(names_src, names_gz):
        pid = r.get("pid") or ""
        if not pid:
            continue
        for key in ("nameAttested", "nameTransliterated", "title"):
            v = (r.get(key) or "").strip()
            if v:
                names_by_pid.setdefault(pid, set()).add(v)

    print("Reading places + writing SQLite ...", flush=True)
    con = sqlite3.connect(out_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("DROP TABLE IF EXISTS places")
    con.execute("""CREATE TABLE places(
        id INTEGER PRIMARY KEY, pid TEXT, title TEXT, description TEXT,
        lat REAL, lng REAL, feature_types TEXT, time_periods TEXT,
        time_range TEXT, uri TEXT, names TEXT)""")
    con.execute("DROP TABLE IF EXISTS fts")
    con.execute("CREATE VIRTUAL TABLE fts USING fts5(title, names, description, tokenize='unicode61')")

    n = 0
    for r in load_csv(places_src, places_gz):
        pid = (r.get("id") or "").strip()
        if not pid:
            continue
        title = (r.get("title") or "").strip()
        names = sorted(names_by_pid.get(pid, set()) - {title})
        names_text = "; ".join(names)
        path = (r.get("path") or "").strip()
        uri = ("https://pleiades.stoa.org" + path) if path.startswith("/") else path
        try:
            lat = float(r["reprLat"]) if r.get("reprLat") else None
            lng = float(r["reprLong"]) if r.get("reprLong") else None
        except ValueError:
            lat = lng = None
        con.execute(
            "INSERT INTO places(pid,title,description,lat,lng,feature_types,"
            "time_periods,time_range,uri,names) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (pid, title, (r.get("description") or "").strip(), lat, lng,
             (r.get("featureTypes") or "").strip(), (r.get("timePeriods") or "").strip(),
             (r.get("timePeriodsRange") or "").strip(), uri, names_text))
        n += 1
    con.execute("INSERT INTO fts(rowid,title,names,description) "
                "SELECT id,title,names,description FROM places")
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM places").fetchone()[0]
    con.execute("VACUUM")
    con.close()
    print(f"\n✓ {total:,} places → {out_path}", flush=True)
    return total


def main():
    ap = argparse.ArgumentParser(description="Build the local Pleiades gazetteer (SQLite+FTS)")
    ap.add_argument("--places", default=None, help="places CSV (or .csv.gz); default: download")
    ap.add_argument("--names", default=None, help="names CSV (or .csv.gz); default: download")
    ap.add_argument("--out", default=str(HERE / "pleiades.sqlite"))
    args = ap.parse_args()

    import tempfile
    tmp = Path(tempfile.mkdtemp())
    if args.places:
        p_src, p_gz = args.places, args.places.endswith(".gz")
    else:
        p_src, p_gz = str(fetch("pleiades-places-latest.csv.gz", tmp / "p.csv.gz")), True
    if args.names:
        n_src, n_gz = args.names, args.names.endswith(".gz")
    else:
        n_src, n_gz = str(fetch("pleiades-names-latest.csv.gz", tmp / "n.csv.gz")), True

    build(p_src, n_src, args.out, p_gz, n_gz)


if __name__ == "__main__":
    main()
