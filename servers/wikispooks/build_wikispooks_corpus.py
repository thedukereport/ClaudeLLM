#!/usr/bin/env python3
"""
Build a searchable local corpus from the WikiSpooks MediaWiki dump.

Streams `backups/wikispooks-database.sql` straight out of wikispooks-latest.zip
(no 4.7 GB temp file), extracts the CURRENT text of every main-namespace article,
and writes a compact SQLite database with an FTS5 full-text index.

Pipeline (single streaming pass; MediaWiki MCR schema):
    mw_page (ns=0, not redirect) --page_latest--> revision id
      --> mw_slots (main role) --slot_content_id--> mw_content
      --content_address 'tt:N'--> mw_text.old_id --old_text/old_flags--> wikitext

Columns are read BY NAME from each CREATE TABLE in the dump, so this is robust
to schema/column-order differences between MediaWiki versions.

Stdlib only. Run on the Mac (no timeouts):
    python3 build_wikispooks_corpus.py \
        --zip /Volumes/PRO-BLADE/WikiSpooks/wikispooks-latest.zip \
        --member backups/wikispooks-database.sql \
        --out /Volumes/PRO-BLADE/WikiSpooks/wikispooks.sqlite
"""

import io
import re
import gzip
import time
import zipfile
import sqlite3
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# MySQL dump tokenizer (byte level — old_text may be binary/gzip)
# ---------------------------------------------------------------------------
_UNESCAPE = {0x30: 0x00, 0x62: 0x08, 0x6e: 0x0a, 0x72: 0x0d,
             0x74: 0x09, 0x5a: 0x1a, 0x5c: 0x5c, 0x27: 0x27, 0x22: 0x22}
_HEX = set(b"0123456789abcdefABCDEF")


def parse_values(payload):
    """Parse the bytes after `VALUES ` into a list of rows (lists of values).
    Strings come back as bytes; numbers as int/float; NULL as None."""
    rows = []
    i, n = 0, len(payload)
    while i < n:
        while i < n and payload[i] != 0x28:  # '('
            i += 1
        if i >= n:
            break
        i += 1
        row = []
        while i < n:
            c = payload[i]
            if c == 0x27:  # '
                i += 1
                buf = bytearray()
                while i < n:
                    ch = payload[i]
                    if ch == 0x5c and i + 1 < n:      # backslash escape
                        buf.append(_UNESCAPE.get(payload[i + 1], payload[i + 1]))
                        i += 2
                        continue
                    if ch == 0x27:                    # closing quote
                        i += 1
                        break
                    buf.append(ch)
                    i += 1
                row.append(bytes(buf))
            elif payload[i:i + 2] == b"0x":
                j = i + 2
                while j < n and payload[j] in _HEX:
                    j += 1
                row.append(bytes.fromhex(payload[i + 2:j].decode()))
                i = j
            else:
                j = i
                while j < n and payload[j] not in (0x2c, 0x29):  # , )
                    j += 1
                tok = payload[i:j].strip()
                if tok == b"NULL":
                    row.append(None)
                else:
                    try:
                        row.append(int(tok))
                    except ValueError:
                        try:
                            row.append(float(tok))
                        except ValueError:
                            row.append(tok)
                i = j
            if i < n and payload[i] == 0x2c:   # ,
                i += 1
                continue
            if i < n and payload[i] == 0x29:   # )
                i += 1
                rows.append(row)
                break
    return rows


def col_map(create_sql):
    """name -> index from a CREATE TABLE block."""
    names = re.findall(rb"^\s+`([A-Za-z0-9_]+)`", create_sql, re.M)
    return {n.decode(): i for i, n in enumerate(names)}


# ---------------------------------------------------------------------------
# Wikitext -> light plaintext (for display + FTS)
# ---------------------------------------------------------------------------
def wikitext_to_text(wt):
    s = wt
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", " ", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", " ", s, flags=re.S)
    for _ in range(6):  # collapse nested templates
        new = re.sub(r"\{\{[^{}]*\}\}", " ", s, flags=re.S)
        if new == s:
            break
        s = new
    s = re.sub(r"\{\|.*?\|\}", " ", s, flags=re.S)          # tables
    s = re.sub(r"\[\[(?:File|Image|Category):[^\]]*\]\]", " ", s, flags=re.I)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)       # [[a|b]] -> b
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)                # [[a]] -> a
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)     # [url text] -> text
    s = re.sub(r"</?[a-zA-Z][^>]*>", " ", s)                 # html tags
    s = re.sub(r"'{2,5}", "", s)                            # bold/italic
    s = re.sub(r"^=+\s*(.*?)\s*=+\s*$", r"\1", s, flags=re.M)  # headings
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def decode_text(old_text, old_flags):
    flags = set((old_flags or b"").decode("ascii", "ignore").split(","))
    data = old_text or b""
    if "gzip" in flags:
        try:
            data = gzip.decompress(data)
        except Exception:
            pass
    enc = "utf-8" if "utf-8" in flags or "utf8" in flags else "latin-1"
    return data.decode(enc, "replace")


# ---------------------------------------------------------------------------
def iter_statements(stream):
    """Yield (table, kind, payload_bytes) for CREATE/INSERT of interest."""
    for raw in stream:
        if raw.startswith(b"INSERT INTO `"):
            end = raw.index(b"`", 12)
            table = raw[12:end].decode()
            v = raw.find(b" VALUES ")
            if v != -1:
                yield table, "insert", raw[v + 8:]
        elif raw.startswith(b"CREATE TABLE `"):
            end = raw.index(b"`", 14)
            yield raw[14:end].decode(), "create", raw  # header line only


def build(zip_path, member, out_path):
    t0 = time.time()
    zf = zipfile.ZipFile(zip_path)
    # We need each table's CREATE block for column maps. CREATE spans many lines,
    # so read the member as a whole line-stream and capture CREATE blocks lazily.
    stream = io.BufferedReader(zf.open(member), buffer_size=1 << 20)

    cols = {}                      # table -> {name: idx}
    content_to_old = {}            # content_id -> old_id  (from mw_content)
    page_rev_title = {}            # page_latest rev -> title (ns=0, not redirect)
    main_role = None
    rev_to_content = {}            # rev -> content_id (main slot, needed revs)
    needed_revs = set()

    # capture CREATE blocks: buffer lines between CREATE TABLE and ') ENGINE'
    capturing = None
    buf = bytearray()

    def finish_create(tbl, block):
        cols[tbl] = col_map(block)

    n_articles = 0
    con = sqlite3.connect(out_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("DROP TABLE IF EXISTS articles")
    con.execute("CREATE TABLE articles(id INTEGER PRIMARY KEY, title TEXT, "
                "wikitext TEXT, plaintext TEXT)")
    con.execute("DROP TABLE IF EXISTS fts")
    con.execute("CREATE VIRTUAL TABLE fts USING fts5(title, plaintext, tokenize='porter unicode61')")

    # First pass composes the mapping; mw_text is last alphabetically, so by the
    # time we reach it we know every needed old_id -> title.
    needed_old = {}                # old_id -> title
    composed = False

    def compose():
        nonlocal composed
        for rev, title in page_rev_title.items():
            cid = rev_to_content.get(rev)
            if cid is None:
                continue
            oid = content_to_old.get(cid)
            if oid is not None:
                needed_old[oid] = title
        composed = True

    for raw in stream:
        if capturing is not None:
            buf += raw
            if raw.startswith(b") ENGINE") or raw.rstrip().endswith(b";"):
                finish_create(capturing, bytes(buf))
                capturing = None
                buf = bytearray()
            continue
        if raw.startswith(b"CREATE TABLE `"):
            end = raw.index(b"`", 14)
            tbl = raw[14:end].decode()
            if tbl in ("mw_page", "mw_content", "mw_slots", "mw_slot_roles", "mw_text"):
                capturing = tbl
                buf = bytearray(raw)
            continue
        if not raw.startswith(b"INSERT INTO `"):
            continue
        end = raw.index(b"`", 13)
        tbl = raw[13:end].decode()
        vpos = raw.find(b" VALUES ")
        if vpos == -1:
            continue
        payload = raw[vpos + 8:]

        if tbl == "mw_content":
            c = cols.get("mw_content", {})
            ci, ai = c.get("content_id", 0), c.get("content_address", 4)
            for r in parse_values(payload):
                addr = r[ai]
                if isinstance(addr, bytes) and addr.startswith(b"tt:"):
                    content_to_old[r[ci]] = int(addr[3:])
        elif tbl == "mw_slot_roles":
            c = cols.get("mw_slot_roles", {})
            ri, ni = c.get("role_id", 0), c.get("role_name", 1)
            for r in parse_values(payload):
                if r[ni] == b"main":
                    main_role = r[ri]
        elif tbl == "mw_page":
            c = cols.get("mw_page", {})
            ns, ti = c.get("page_namespace", 1), c.get("page_title", 2)
            red, lat = c.get("page_is_redirect", 4), c.get("page_latest", 8)
            for r in parse_values(payload):
                if r[ns] == 0 and r[red] == 0:
                    page_rev_title[r[lat]] = r[ti].decode("utf-8", "replace")
                    needed_revs.add(r[lat])
        elif tbl == "mw_slots":
            c = cols.get("mw_slots", {})
            sr, ro, sc = c.get("slot_revision_id", 0), c.get("slot_role_id", 1), c.get("slot_content_id", 2)
            for r in parse_values(payload):
                if r[sr] in needed_revs and (main_role is None or r[ro] == main_role):
                    rev_to_content[r[sr]] = r[sc]
        elif tbl == "mw_text":
            if not composed:
                compose()
                print(f"  composed mapping: {len(needed_old):,} articles to fetch "
                      f"({time.time()-t0:.0f}s)", flush=True)
            c = cols.get("mw_text", {})
            oi = c.get("old_id", 0); tx = c.get("old_text", 1); fl = c.get("old_flags", 2)
            batch = []
            for r in parse_values(payload):
                title = needed_old.get(r[oi])
                if title is None:
                    continue
                wt = decode_text(r[tx], r[fl] if fl < len(r) else b"utf-8")
                pt = wikitext_to_text(wt)
                batch.append((title, wt, pt))
            if batch:
                con.executemany(
                    "INSERT INTO articles(title,wikitext,plaintext) VALUES(?,?,?)", batch)
                n_articles += len(batch)
                if n_articles % 4000 < len(batch):
                    print(f"  articles written: {n_articles:,} ({time.time()-t0:.0f}s)", flush=True)

    # populate FTS from articles in one shot (robust)
    con.execute("DELETE FROM fts")
    con.execute("INSERT INTO fts(rowid,title,plaintext) SELECT id,title,plaintext FROM articles")
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    con.execute("VACUUM")
    con.close()
    print(f"\n✓ Done in {time.time()-t0:.0f}s — {total:,} articles → {out_path}", flush=True)
    return total


def main():
    ap = argparse.ArgumentParser(description="Build WikiSpooks SQLite+FTS corpus from the MediaWiki dump")
    ap.add_argument("--zip", default="/Volumes/PRO-BLADE/WikiSpooks/wikispooks-latest.zip")
    ap.add_argument("--member", default="backups/wikispooks-database.sql")
    ap.add_argument("--out", default="/Volumes/PRO-BLADE/WikiSpooks/wikispooks.sqlite")
    args = ap.parse_args()
    build(args.zip, args.member, args.out)


if __name__ == "__main__":
    main()
